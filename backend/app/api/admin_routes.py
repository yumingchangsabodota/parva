"""Admin API routes for platform configuration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import require_admin
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def get_app_state():
    from app.main import app_state
    return app_state


# ── Models ────────────────────────────────────────────────────────────

class AddModelRequest(BaseModel):
    model_name: str
    litellm_model: str  # e.g. "openai/gpt-4o"
    api_key: str | None = None  # optional override


class SetDefaultModelRequest(BaseModel):
    chat_model: str | None = None
    image_model: str | None = None


@router.get("/models")
async def list_models(state=Depends(get_app_state)):
    """List all models configured in LiteLLM."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.litellm_base_url.rstrip('/v1')}/model/info",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Failed to list models from LiteLLM")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/models")
async def add_model(req: AddModelRequest, state=Depends(get_app_state)):
    """Add a new model to LiteLLM."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "model_name": req.model_name,
        "litellm_params": {
            "model": req.litellm_model,
        },
        "model_info": {
            "access_groups": ["public"],
        },
    }
    if req.api_key:
        payload["litellm_params"]["api_key"] = req.api_key

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.litellm_base_url.rstrip('/v1')}/model/new",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Failed to add model")
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, state=Depends(get_app_state)):
    """Delete a model from LiteLLM."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.litellm_base_url.rstrip('/v1')}/model/delete",
                json={"id": model_id},
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Failed to delete model")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/models/defaults")
async def get_default_models(state=Depends(get_app_state)):
    """Get the platform default models."""
    defaults = await state.redis.get_json("parva:admin:default_models")
    settings = get_settings()
    return defaults or {
        "chat_model": settings.default_chat_model,
        "image_model": settings.default_image_model,
    }


@router.put("/models/defaults")
async def set_default_models(req: SetDefaultModelRequest, state=Depends(get_app_state)):
    """Set the platform default models."""
    defaults = {
        "chat_model": req.chat_model,
        "image_model": req.image_model,
    }
    await state.redis.set_json("parva:admin:default_models", defaults)
    return defaults


# ── Skills ────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills(state=Depends(get_app_state)):
    """List all skills with full details."""
    return state.skill_registry.list_skills()


@router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str, state=Depends(get_app_state)):
    """Delete a custom (non-builtin) skill."""
    try:
        state.skill_registry.delete_skill(skill_name)
        state.agent.invalidate_cache()
        return {"status": "deleted", "name": skill_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Providers ─────────────────────────────────────────────────────────

class ProviderKeyRequest(BaseModel):
    provider: str  # e.g. "openai", "anthropic"
    api_key: str


@router.get("/providers")
async def list_providers(state=Depends(get_app_state)):
    """List configured LLM providers and whether they have keys set."""
    providers = await state.redis.get_json("parva:admin:providers") or {}
    # Return provider names with masked key status (never expose actual keys)
    return [
        {
            "provider": name,
            "has_key": bool(info.get("has_key")),
            "env_var": info.get("env_var", ""),
        }
        for name, info in providers.items()
    ] if providers else [
        {"provider": "openai", "has_key": False, "env_var": "OPENAI_API_KEY"},
        {"provider": "anthropic", "has_key": False, "env_var": "ANTHROPIC_API_KEY"},
        {"provider": "google", "has_key": False, "env_var": "GOOGLE_API_KEY"},
        {"provider": "azure", "has_key": False, "env_var": "AZURE_API_KEY"},
    ]


@router.put("/providers")
async def set_provider_key(req: ProviderKeyRequest, state=Depends(get_app_state)):
    """Set an LLM provider API key. Stored securely and passed to LiteLLM."""
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "azure": "AZURE_API_KEY",
    }
    env_var = env_map.get(req.provider)
    if not env_var:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    # Store provider status in Redis (key itself stored as Redis secret)
    providers = await state.redis.get_json("parva:admin:providers") or {}
    providers[req.provider] = {
        "has_key": True,
        "env_var": env_var,
    }
    await state.redis.set_json("parva:admin:providers", providers)

    # Store the actual key securely in Redis
    await state.redis.client.set(f"parva:secret:{env_var}", req.api_key)

    return {"status": "ok", "provider": req.provider}


# ── System ────────────────────────────────────────────────────────────

@router.get("/health")
async def system_health(state=Depends(get_app_state)):
    """Check health of all platform services."""
    settings = get_settings()
    checks: dict[str, Any] = {}

    # Redis
    try:
        await state.redis.client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # MinIO
    try:
        buckets = await state.minio.client.list_buckets()
        checks["minio"] = {"status": "healthy", "buckets": len(buckets)}
    except Exception as e:
        checks["minio"] = {"status": "unhealthy", "error": str(e)}

    # LiteLLM
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.litellm_base_url.rstrip('/v1')}/health",
                timeout=5,
            )
            checks["litellm"] = {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
            }
    except Exception as e:
        checks["litellm"] = {"status": "unhealthy", "error": str(e)}

    # PostgreSQL (via checkpointer)
    try:
        # Simple query to verify connectivity
        graph = state.agent.get_graph()
        config = {"configurable": {"thread_id": "__health_check__"}}
        await graph.aget_state(config)
        checks["postgresql"] = {"status": "healthy"}
    except Exception as e:
        checks["postgresql"] = {"status": "unhealthy", "error": str(e)}

    # Active executor containers
    try:
        containers = await state.executor.list_containers()
        checks["executors"] = {
            "status": "healthy",
            "active_containers": len(containers),
        }
    except Exception as e:
        checks["executors"] = {"status": "unknown", "error": str(e)}

    all_healthy = all(c.get("status") == "healthy" for c in checks.values()
                      if c.get("status") != "unknown")

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": checks,
    }
