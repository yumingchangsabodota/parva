"""
Core LangGraph agent using create_react_agent (DeepAgent pattern).

The agent has access to:
1. execute_skill — run any registered skill in an isolated container
2. generate_image — generate images via LiteLLM image models
3. read_file — read uploaded file contents

All heavy work is delegated to skills to keep context short.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent

from app.core.config import get_settings
from app.services.executor import ExecutorService
from app.services.minio_service import MinIOService
from app.services.notification_service import NotificationService
from app.services.redis_service import RedisService
from app.services.skill_registry import SkillRegistry
from app.agent.tools import (
    create_execute_skill_tool,
    create_generate_image_tool,
    create_read_file_tool,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are Parva, an AI assistant running on an enterprise platform.
You help users by understanding their requests and executing skills in isolated environments.

## Capabilities
- Execute skills (code, analysis, data processing, etc.) in sandboxed containers
- Generate images using AI image models
- Read and analyze uploaded files of any type
- Each user has a persistent workspace — installed dependencies and files persist between executions

## Available Skills
{skills_description}

## Guidelines
1. When a user asks you to do something that matches a skill, use `execute_skill` with the right params.
2. For file processing, first use `read_file` to understand the file, then use `execute_skill` to process it.
3. For image generation, use `generate_image` with a detailed prompt.
4. Be concise. Summarize skill results rather than dumping raw output.
5. If a skill fails, explain the error and suggest fixes.
6. For long-running tasks, let the user know it may take a moment.
7. You can chain multiple skills together for complex workflows.
"""


class AgentManager:
    """Manages the LangGraph agent instance and its dependencies."""

    def __init__(
        self,
        redis: RedisService,
        minio: MinIOService,
        skill_registry: SkillRegistry,
        executor: ExecutorService,
        notification: NotificationService,
        checkpointer: AsyncPostgresSaver,
    ) -> None:
        self.redis = redis
        self.minio = minio
        self.skill_registry = skill_registry
        self.executor = executor
        self.notification = notification
        self.checkpointer = checkpointer
        self._graphs: dict[str, Any] = {}  # Cache by model name

    def _create_llm(self, model: str | None = None) -> ChatOpenAI:
        settings = get_settings()
        return ChatOpenAI(
            model=model or settings.default_chat_model,
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key,
            streaming=True,
        )

    def _create_tools(self):
        execute_skill = create_execute_skill_tool(
            self.executor, self.skill_registry, self.minio, self.redis
        )
        generate_image = create_generate_image_tool(self.redis, self.minio)
        read_file = create_read_file_tool(self.minio)
        return [execute_skill, generate_image, read_file]

    def get_graph(self, model: str | None = None):
        """Get or create a compiled graph for the given model."""
        settings = get_settings()
        model_name = model or settings.default_chat_model

        if model_name not in self._graphs:
            llm = self._create_llm(model_name)
            tools = self._create_tools()

            skills_desc = self.skill_registry.build_skill_descriptions()
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                skills_description=skills_desc
            )

            graph = create_react_agent(
                model=llm,
                tools=tools,
                checkpointer=self.checkpointer,
                prompt=system_prompt,
            )
            self._graphs[model_name] = graph

        return self._graphs[model_name]

    def invalidate_cache(self) -> None:
        """Clear cached graphs (e.g., after skill registry changes)."""
        self._graphs.clear()

    async def invoke(
        self,
        message: str,
        thread_id: str,
        user_id: str,
        model: str | None = None,
        image_model: str | None = None,
        file_keys: list[str] | None = None,
    ):
        """Invoke the agent with a user message. Returns the full response."""
        graph = self.get_graph(model)

        # Build user message with file references
        content = message
        if file_keys:
            files_info = ", ".join(file_keys)
            content += f"\n\n[Attached files: {files_info}]"

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "image_model": image_model or get_settings().default_image_model,
            }
        }

        # Inject config into tools so they can access user context
        for t in graph.get_graph().nodes.values():
            pass  # Tools get config from RunnableConfig

        input_msg = {"messages": [{"role": "user", "content": content}]}

        result = await graph.ainvoke(input_msg, config=config)
        return result

    async def stream(
        self,
        message: str,
        thread_id: str,
        user_id: str,
        model: str | None = None,
        image_model: str | None = None,
        file_keys: list[str] | None = None,
    ):
        """Stream the agent response. Yields events for real-time UI updates."""
        graph = self.get_graph(model)

        content = message
        if file_keys:
            files_info = ", ".join(file_keys)
            content += f"\n\n[Attached files: {files_info}]"

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "image_model": image_model or get_settings().default_image_model,
            }
        }

        input_msg = {"messages": [{"role": "user", "content": content}]}

        token_count = 0
        async for event in graph.astream_events(input_msg, config=config, version="v2"):
            yield event
            # Track token count for long-output notification
            if event.get("event") == "on_chat_model_stream":
                token_count += 1

        # Notify if it was a long response
        if token_count > 500:
            await self.notification.notify_agent_done(user_id, thread_id)
