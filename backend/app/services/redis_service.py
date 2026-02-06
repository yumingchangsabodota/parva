"""Redis pub/sub and caching service."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from app.core.config import get_settings


class RedisService:
    def __init__(self) -> None:
        s = get_settings()
        self.redis = aioredis.from_url(s.redis_url, decode_responses=True)

    # ── Pub/Sub for real-time events ──────────────────────────────────
    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        await self.redis.publish(channel, json.dumps(data))

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    def user_channel(self, user_id: str) -> str:
        return f"parva:user:{user_id}:events"

    def execution_channel(self, execution_id: str) -> str:
        return f"parva:exec:{execution_id}:progress"

    # ── Simple KV for execution state ─────────────────────────────────
    async def set_json(self, key: str, data: dict, ttl: int | None = None) -> None:
        val = json.dumps(data)
        if ttl:
            await self.redis.setex(key, ttl, val)
        else:
            await self.redis.set(key, val)

    async def get_json(self, key: str) -> dict | None:
        val = await self.redis.get(key)
        return json.loads(val) if val else None

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    # ── User model preferences ────────────────────────────────────────
    async def set_user_prefs(self, user_id: str, prefs: dict) -> None:
        await self.set_json(f"parva:user:{user_id}:prefs", prefs)

    async def get_user_prefs(self, user_id: str) -> dict | None:
        return await self.get_json(f"parva:user:{user_id}:prefs")

    async def close(self) -> None:
        await self.redis.aclose()
