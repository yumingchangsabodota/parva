"""
Single unified tool for skill execution.

Design philosophy: Keep the agent's context short by having ONE tool that can
execute any skill. The agent decides which skill to invoke and with what params.
The tool handles packaging, sending to the executor, and streaming progress.

LangGraph's create_react_agent passes RunnableConfig to tools automatically.
We extract user_id/thread_id from config["configurable"].
"""

from __future__ import annotations

import base64
import io
import json
import logging
import uuid
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExecuteSkillInput(BaseModel):
    """Input for the execute_skill tool."""
    skill_name: str = Field(description="Name of the skill to execute")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the skill",
    )
    file_keys: list[str] = Field(
        default_factory=list,
        description="MinIO file keys to make available to the skill",
    )


def create_execute_skill_tool(executor_service, skill_registry, minio_service, redis_service):
    """Factory that creates the execute_skill tool with injected services."""

    @tool("execute_skill", args_schema=ExecuteSkillInput)
    async def execute_skill(
        skill_name: str,
        params: dict[str, Any] = {},
        file_keys: list[str] = [],
        *,
        config: RunnableConfig,
    ) -> str:
        """Execute a skill in the user's isolated environment.

        Use this tool to run any available skill. The skill runs in a sandboxed
        container with the user's persistent workspace. Results are returned
        as a JSON string.

        Available skills are listed in the system prompt. Pass the skill name
        and any required parameters.
        """
        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id", "default")
        thread_id = configurable.get("thread_id", "default")

        # Validate skill exists
        manifest = skill_registry.get_skill(skill_name)
        if not manifest:
            available = [s.name for s in skill_registry.list_skills()]
            return json.dumps({
                "error": f"Skill '{skill_name}' not found. Available: {available}"
            })

        execution_id = str(uuid.uuid4())

        # Publish progress start
        await redis_service.publish(
            redis_service.user_channel(user_id),
            {
                "type": "execution_progress",
                "thread_id": thread_id,
                "data": {
                    "execution_id": execution_id,
                    "skill_name": skill_name,
                    "status": "queued",
                    "progress_pct": 0,
                    "current_step": "Preparing skill execution...",
                },
            },
        )

        # Get skill source
        skill_source_archive = skill_registry.get_skill_source_archive(skill_name)
        if not skill_source_archive:
            return json.dumps({"error": f"Skill source not found for '{skill_name}'"})

        # Fetch files from MinIO if needed
        files = {}
        for key in file_keys:
            try:
                data = await minio_service.download_file(key)
                filename = key.split("/")[-1]
                files[filename] = data
            except Exception as e:
                logger.warning(f"Failed to fetch file {key}: {e}")

        # Execute in the user's container
        result = await executor_service.execute_skill(
            user_id=user_id,
            execution_id=execution_id,
            skill_name=skill_name,
            skill_source=base64.b64encode(skill_source_archive).decode(),
            entrypoint=manifest.entrypoint,
            params=params,
            dependencies=manifest.dependencies,
            files=files,
            timeout=manifest.timeout_seconds,
        )

        # Publish completion notification
        await redis_service.publish(
            redis_service.user_channel(user_id),
            {
                "type": "execution_done",
                "thread_id": thread_id,
                "data": {
                    "execution_id": execution_id,
                    "skill_name": skill_name,
                    "status": result.status.value,
                    "result": result.result,
                    "error": result.error,
                },
            },
        )

        return json.dumps({
            "execution_id": execution_id,
            "status": result.status.value,
            "result": result.result,
            "error": result.error,
            "logs": result.logs[-2000:] if result.logs else "",
        })

    return execute_skill


class GenerateImageInput(BaseModel):
    """Input for image generation."""
    prompt: str = Field(description="Description of the image to generate")
    size: str = Field(default="1024x1024", description="Image size")
    quality: str = Field(default="standard", description="Image quality")


def create_generate_image_tool(redis_service, minio_service):
    """Factory that creates an image generation tool."""

    @tool("generate_image", args_schema=GenerateImageInput)
    async def generate_image(
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        *,
        config: RunnableConfig,
    ) -> str:
        """Generate an image using the configured image model.

        Provide a detailed description of the image you want to create.
        Returns a MinIO URL to the generated image.
        """
        from openai import AsyncOpenAI
        from app.core.config import get_settings

        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id", "default")
        image_model = configurable.get("image_model", get_settings().default_image_model)

        settings = get_settings()
        client = AsyncOpenAI(
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key,
        )

        try:
            response = await client.images.generate(
                model=image_model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                response_format="b64_json",
            )

            image_data = base64.b64decode(response.data[0].b64_json)

            file_ref = await minio_service.upload_file(
                user_id=user_id,
                filename=f"generated_{uuid.uuid4().hex[:8]}.png",
                data=io.BytesIO(image_data),
                content_type="image/png",
                size=len(image_data),
            )

            url = await minio_service.get_presigned_url(file_ref.key)

            return json.dumps({
                "status": "success",
                "image_url": url,
                "file_key": file_ref.key,
                "prompt": prompt,
            })
        except Exception as e:
            logger.exception("Image generation failed")
            return json.dumps({"error": str(e)})

    return generate_image


class ReadFileInput(BaseModel):
    """Input for reading uploaded files."""
    file_key: str = Field(description="MinIO object key of the file")
    max_chars: int = Field(default=10000, description="Max characters to return for text files")


def create_read_file_tool(minio_service):
    """Factory that creates a file reading tool."""

    @tool("read_file", args_schema=ReadFileInput)
    async def read_file(file_key: str, max_chars: int = 10000) -> str:
        """Read the contents of an uploaded file.

        For text-based files, returns the content as text.
        For binary files, returns metadata about the file.
        Use this to understand file contents before processing with skills.
        """
        try:
            data = await minio_service.download_file(file_key)
            filename = file_key.split("/")[-1]

            try:
                text = data.decode("utf-8")
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n... [truncated, {len(data)} bytes total]"
                return json.dumps({
                    "filename": filename,
                    "type": "text",
                    "size": len(data),
                    "content": text,
                })
            except UnicodeDecodeError:
                return json.dumps({
                    "filename": filename,
                    "type": "binary",
                    "size": len(data),
                    "content": f"Binary file, {len(data)} bytes. Pass file_key to execute_skill to process.",
                })
        except Exception as e:
            return json.dumps({"error": str(e)})

    return read_file
