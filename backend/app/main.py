"""Parva — AI Agent Chatbot Platform."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings
from app.services.redis_service import RedisService
from app.services.minio_service import MinIOService
from app.services.executor import ExecutorService
from app.services.notification_service import NotificationService
from app.services.skill_registry import SkillRegistry
from app.agent.graph import AgentManager
from app.api.routes import router
from app.api.admin_routes import router as admin_router
from app.api.auth import router as auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AppState:
    redis: RedisService
    minio: MinIOService
    executor: ExecutorService
    notification: NotificationService
    skill_registry: SkillRegistry
    agent: AgentManager
    checkpointer: AsyncPostgresSaver
    cleanup_task: asyncio.Task | None = None


app_state: AppState | None = None


async def _periodic_cleanup(executor: ExecutorService, interval: int = 300):
    """Periodically clean up idle executor containers."""
    while True:
        try:
            cleaned = await executor.cleanup_idle_containers()
            if cleaned:
                logger.info(f"Cleaned up {cleaned} idle containers")
        except Exception:
            logger.exception("Error during container cleanup")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_state

    settings = get_settings()
    logger.info("Starting Parva platform...")

    # Initialize services
    redis = RedisService()
    minio = MinIOService()
    skill_registry = SkillRegistry()
    executor = ExecutorService(redis)
    notification = NotificationService(redis)

    # Initialize LangGraph Postgres checkpointer
    async with AsyncPostgresSaver.from_conn_string(settings.postgres_dsn) as checkpointer:
        await checkpointer.setup()

        # Initialize agent manager
        agent = AgentManager(
            redis=redis,
            minio=minio,
            skill_registry=skill_registry,
            executor=executor,
            notification=notification,
            checkpointer=checkpointer,
        )

        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(_periodic_cleanup(executor))

        app_state = AppState(
            redis=redis,
            minio=minio,
            executor=executor,
            notification=notification,
            skill_registry=skill_registry,
            agent=agent,
            checkpointer=checkpointer,
            cleanup_task=cleanup_task,
        )

        logger.info("Parva platform ready!")
        yield

        # Shutdown
        logger.info("Shutting down Parva platform...")
        cleanup_task.cancel()
        await redis.close()


app = FastAPI(
    title="Parva",
    description="AI Agent Chatbot Platform with isolated skill execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)
app.include_router(admin_router)
