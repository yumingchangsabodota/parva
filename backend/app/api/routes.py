"""FastAPI routes for the Parva platform."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ExecutionProgress,
    FileUploadResponse,
    MessageRole,
    ModelInfo,
    SkillImportRequest,
    SkillInfo,
    ThreadSummary,
    UserModelPrefs,
    WSEvent,
    WSEventType,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_app_state():
    """Dependency to get app state — injected from main.py lifespan."""
    from app.main import app_state
    return app_state


# ── Chat ────────────────────────────────────────────────────────────────

@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, state=Depends(get_app_state)):
    """Send a message and get a response (non-streaming)."""
    thread_id = req.thread_id or str(uuid.uuid4())

    result = await state.agent.invoke(
        message=req.message,
        thread_id=thread_id,
        user_id=req.user_id,
        model=req.model,
        image_model=req.image_model,
        file_keys=req.files,
    )

    # Extract the last assistant message
    messages = result.get("messages", [])
    last_msg = None
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "ai" and m.content:
            last_msg = m
            break

    content = last_msg.content if last_msg else "I couldn't generate a response."

    return ChatResponse(
        thread_id=thread_id,
        message=ChatMessage(role=MessageRole.assistant, content=content),
    )


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, state=Depends(get_app_state)):
    """Stream a chat response using Server-Sent Events."""
    thread_id = req.thread_id or str(uuid.uuid4())

    async def event_generator():
        # Send thread_id first
        yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': thread_id})}\n\n"

        full_content = ""
        try:
            async for event in state.agent.stream(
                message=req.message,
                thread_id=thread_id,
                user_id=req.user_id,
                model=req.model,
                image_model=req.image_model,
                file_keys=req.files,
            ):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        full_content += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    output = event.get("data", {}).get("output", "")
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'output': str(output)[:500]})}\n\n"

        except Exception as e:
            logger.exception("Streaming error")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Chat History ────────────────────────────────────────────────────────

@router.get("/api/threads", response_model=list[ThreadSummary])
async def list_threads(user_id: str = Query(...), state=Depends(get_app_state)):
    """List chat threads for a user from the checkpointer."""
    # Query threads from Postgres via the checkpointer
    threads = []
    try:
        async with state.db_pool.connection() as conn:
            rows = await conn.execute(
                """
                SELECT DISTINCT thread_id, metadata, updated_at
                FROM checkpoints
                WHERE metadata->>'user_id' = $1
                ORDER BY updated_at DESC
                LIMIT 50
                """,
                [user_id],
            )
            async for row in rows:
                threads.append(ThreadSummary(
                    thread_id=row[0],
                    title=row[1].get("title") if row[1] else None,
                    updated_at=row[2],
                ))
    except Exception:
        # Checkpointer table might not exist yet or have different schema
        # Fall back to Redis-cached thread list
        cached = await state.redis.get_json(f"parva:user:{user_id}:threads")
        if cached:
            threads = [ThreadSummary(**t) for t in cached]
    return threads


@router.get("/api/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: str,
    user_id: str = Query(...),
    state=Depends(get_app_state),
):
    """Get messages for a thread from the LangGraph checkpointer."""
    config = {"configurable": {"thread_id": thread_id}}
    graph = state.agent.get_graph()

    try:
        checkpoint = await graph.aget_state(config)
        if not checkpoint or not checkpoint.values:
            return {"messages": []}

        messages = []
        for msg in checkpoint.values.get("messages", []):
            role = "assistant"
            if hasattr(msg, "type"):
                if msg.type == "human":
                    role = "user"
                elif msg.type == "ai":
                    role = "assistant"
                elif msg.type == "tool":
                    role = "tool"
                elif msg.type == "system":
                    role = "system"

            content = msg.content if hasattr(msg, "content") else str(msg)
            messages.append({
                "role": role,
                "content": content,
                "metadata": msg.additional_kwargs if hasattr(msg, "additional_kwargs") else {},
            })

        return {"messages": messages}
    except Exception as e:
        logger.exception("Failed to get thread messages")
        return {"messages": []}


# ── Files ───────────────────────────────────────────────────────────────

@router.post("/api/files/upload", response_model=FileUploadResponse)
async def upload_files(
    user_id: str = Query(...),
    files: list[UploadFile] = File(...),
    state=Depends(get_app_state),
):
    """Upload files to MinIO storage."""
    refs = []
    for f in files:
        data = await f.read()
        import io
        ref = await state.minio.upload_file(
            user_id=user_id,
            filename=f.filename or "unnamed",
            data=io.BytesIO(data),
            content_type=f.content_type or "application/octet-stream",
            size=len(data),
        )
        refs.append(ref)
    return FileUploadResponse(files=refs)


@router.get("/api/files/{file_key:path}/url")
async def get_file_url(file_key: str, state=Depends(get_app_state)):
    """Get a presigned URL for a file."""
    url = await state.minio.get_presigned_url(file_key)
    return {"url": url}


# ── Skills ──────────────────────────────────────────────────────────────

@router.get("/api/skills", response_model=list[SkillInfo])
async def list_skills(state=Depends(get_app_state)):
    """List all available skills."""
    return state.skill_registry.list_skills()


@router.post("/api/skills/import", response_model=SkillInfo)
async def import_skill(req: SkillImportRequest, state=Depends(get_app_state)):
    """Import a skill from a URL."""
    try:
        skill = await state.skill_registry.import_skill_from_url(req.url, req.name)
        # Invalidate agent graph cache so new skill is picked up
        state.agent.invalidate_cache()
        return skill
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Models ──────────────────────────────────────────────────────────────

@router.get("/api/models", response_model=list[ModelInfo])
async def list_models(state=Depends(get_app_state)):
    """List available models from LiteLLM."""
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )
    try:
        response = await client.models.list()
        models = []
        for m in response.data:
            model_type = "image" if any(
                kw in m.id.lower() for kw in ["dall-e", "sdxl", "stable", "flux", "imagen"]
            ) else "chat"
            models.append(ModelInfo(id=m.id, name=m.id, type=model_type))
        return models
    except Exception as e:
        logger.warning(f"Failed to list models from LiteLLM: {e}")
        # Return defaults
        return [
            ModelInfo(id=settings.default_chat_model, name=settings.default_chat_model, type="chat"),
            ModelInfo(id=settings.default_image_model, name=settings.default_image_model, type="image"),
        ]


@router.get("/api/models/preferences")
async def get_model_preferences(
    user_id: str = Query(...), state=Depends(get_app_state)
):
    prefs = await state.redis.get_user_prefs(user_id)
    return prefs or {"chat_model": None, "image_model": None}


@router.put("/api/models/preferences")
async def set_model_preferences(
    prefs: UserModelPrefs,
    user_id: str = Query(...),
    state=Depends(get_app_state),
):
    await state.redis.set_user_prefs(user_id, prefs.model_dump())
    return {"status": "ok"}


# ── WebSocket ───────────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket for real-time notifications and execution progress."""
    await websocket.accept()
    from app.main import app_state

    redis = app_state.redis
    channel = redis.user_channel(user_id)

    try:
        # Listen to Redis pub/sub and forward to WebSocket
        async for event in redis.subscribe(channel):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for user {user_id}")
