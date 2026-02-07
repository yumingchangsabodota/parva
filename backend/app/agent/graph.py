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


def serialize_message(msg) -> dict[str, Any]:
    """Serialize a LangChain message object to a JSON-safe dict."""
    data: dict[str, Any] = {
        "id": getattr(msg, "id", None),
        "content": msg.content if hasattr(msg, "content") else str(msg),
    }

    # Determine role from message type
    msg_type = getattr(msg, "type", None)
    if msg_type == "human":
        data["role"] = "user"
    elif msg_type == "ai":
        data["role"] = "assistant"
        # Include tool_calls if present
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", ""),
                    "name": tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", ""),
                    "args": tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}),
                }
                for tc in tool_calls
            ]
    elif msg_type == "tool":
        data["role"] = "tool"
        data["tool_call_id"] = getattr(msg, "tool_call_id", None)
        data["name"] = getattr(msg, "name", None)
    elif msg_type == "system":
        data["role"] = "system"
    else:
        data["role"] = "assistant"

    additional = getattr(msg, "additional_kwargs", {})
    if additional:
        data["additional_kwargs"] = additional

    resp_meta = getattr(msg, "response_metadata", None)
    if resp_meta:
        data["response_metadata"] = resp_meta

    return data


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

    def _build_config(
        self,
        thread_id: str,
        user_id: str,
        image_model: str | None = None,
    ) -> dict:
        return {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "image_model": image_model or get_settings().default_image_model,
            }
        }

    def _build_input(self, message: str, file_keys: list[str] | None = None) -> dict:
        content = message
        if file_keys:
            files_info = ", ".join(file_keys)
            content += f"\n\n[Attached files: {files_info}]"
        return {"messages": [{"role": "user", "content": content}]}

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
        config = self._build_config(thread_id, user_id, image_model)
        input_msg = self._build_input(message, file_keys)
        return await graph.ainvoke(input_msg, config=config)

    async def stream(
        self,
        message: str,
        thread_id: str,
        user_id: str,
        model: str | None = None,
        image_model: str | None = None,
        file_keys: list[str] | None = None,
    ):
        """
        Stream using stream_mode=["messages", "updates"].

        Yields (mode, chunk) tuples:
        - ("messages", (AIMessageChunk|ToolMessage, metadata)) — token-level
        - ("updates", {node_name: {state_delta}}) — node-level (tool calls, results)
        """
        graph = self.get_graph(model)
        config = self._build_config(thread_id, user_id, image_model)
        input_msg = self._build_input(message, file_keys)

        token_count = 0
        async for mode, chunk in graph.astream(
            input_msg, config=config, stream_mode=["messages", "updates"]
        ):
            yield mode, chunk
            if mode == "messages":
                msg_chunk, _ = chunk
                if hasattr(msg_chunk, "content") and msg_chunk.content:
                    token_count += 1

        if token_count > 500:
            await self.notification.notify_agent_done(user_id, thread_id)

    async def get_thread_messages(self, thread_id: str, model: str | None = None) -> list[dict]:
        """Get all messages for a thread from the checkpointer."""
        graph = self.get_graph(model)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            state = await graph.aget_state(config)
            if not state or not state.values:
                return []
            return [
                serialize_message(msg)
                for msg in state.values.get("messages", [])
            ]
        except Exception as e:
            logger.exception("Failed to get thread messages")
            return []
