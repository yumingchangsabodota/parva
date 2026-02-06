"""
Notification service — handles user notifications via Redis pub/sub + WebSocket.

Notifications are triggered:
1. When a skill execution completes (especially long-running ones)
2. When the agent finishes a long output
3. When errors occur during execution
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.schemas import WSEvent, WSEventType
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, redis: RedisService) -> None:
        self.redis = redis

    async def notify_user(
        self,
        user_id: str,
        message: str,
        thread_id: str | None = None,
        notification_type: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification to a user via their Redis channel."""
        event = WSEvent(
            type=WSEventType.notification,
            thread_id=thread_id,
            data={
                "message": message,
                "notification_type": notification_type,
                **(data or {}),
            },
        )
        await self.redis.publish(
            self.redis.user_channel(user_id),
            event.model_dump(mode="json"),
        )

    async def notify_execution_complete(
        self,
        user_id: str,
        thread_id: str,
        skill_name: str,
        execution_id: str,
        success: bool,
    ) -> None:
        """Notify user when a skill execution finishes."""
        status = "completed" if success else "failed"
        await self.notify_user(
            user_id=user_id,
            thread_id=thread_id,
            message=f"Skill '{skill_name}' {status}",
            notification_type="execution_complete",
            data={
                "execution_id": execution_id,
                "skill_name": skill_name,
                "success": success,
            },
        )

    async def notify_agent_done(
        self,
        user_id: str,
        thread_id: str,
    ) -> None:
        """Notify user when the agent finishes a long response."""
        await self.notify_user(
            user_id=user_id,
            thread_id=thread_id,
            message="Agent has finished responding",
            notification_type="agent_done",
        )
