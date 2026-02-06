"""
Docker-based isolated execution environment manager.

Architecture:
- Each user gets a persistent "sidecar" container that stays alive.
- The container has a mounted workspace volume for persistent state.
- Skills are copied into the workspace and executed inside the container.
- Dependencies are installed once and cached in the container filesystem.
- Containers idle-timeout after inactivity and are reclaimed.
- A lightweight HTTP server inside the container receives execution commands.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import docker
import httpx

from app.core.config import get_settings
from app.models.schemas import ExecutionProgress, ExecutionStatus
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


class ExecutorService:
    """Manages per-user Docker execution containers."""

    def __init__(self, redis: RedisService) -> None:
        self.settings = get_settings()
        self.docker = docker.from_env()
        self.redis = redis
        self._http = httpx.AsyncClient(timeout=600)

    # ── Container lifecycle ────────────────────────────────────────────

    def _container_name(self, user_id: str) -> str:
        return f"parva-exec-{user_id[:12]}"

    def _workspace_path(self, user_id: str) -> str:
        return f"{self.settings.executor_workspace_base}/{user_id}"

    async def _get_or_create_container(self, user_id: str) -> dict:
        """Get existing container or create a new one. Returns container info."""
        name = self._container_name(user_id)

        # Check Redis for cached container info
        info = await self.redis.get_json(f"parva:container:{user_id}")
        if info:
            try:
                container = self.docker.containers.get(name)
                if container.status == "running":
                    await self._touch_activity(user_id)
                    return info
                # Container exists but stopped — restart it
                container.start()
                await self._touch_activity(user_id)
                return info
            except docker.errors.NotFound:
                pass  # Container was removed, recreate

        # Create workspace directory
        workspace = self._workspace_path(user_id)

        # Create the container
        container = self.docker.containers.run(
            self.settings.executor_image,
            detach=True,
            name=name,
            hostname=name,
            network=self.settings.executor_network,
            mem_limit=self.settings.executor_memory_limit,
            nano_cpus=int(self.settings.executor_cpu_limit * 1e9),
            volumes={
                workspace: {"bind": "/workspace", "mode": "rw"},
            },
            environment={
                "USER_ID": user_id,
                "MINIO_ENDPOINT": self.settings.minio_endpoint,
                "MINIO_ACCESS_KEY": self.settings.minio_access_key,
                "MINIO_SECRET_KEY": self.settings.minio_secret_key,
                "MINIO_BUCKET": self.settings.minio_bucket,
                "REDIS_URL": self.settings.redis_url,
            },
            restart_policy={"Name": "unless-stopped"},
            labels={"parva.user": user_id, "parva.role": "executor"},
        )

        info = {
            "container_id": container.id,
            "container_name": name,
            "user_id": user_id,
            "host": name,  # Docker DNS on shared network
            "port": 8100,
        }
        await self.redis.set_json(f"parva:container:{user_id}", info)
        await self._touch_activity(user_id)

        # Wait for executor HTTP server to be ready
        await self._wait_ready(info)
        return info

    async def _wait_ready(self, info: dict, retries: int = 30) -> None:
        url = f"http://{info['host']}:{info['port']}/health"
        for i in range(retries):
            try:
                resp = await self._http.get(url)
                if resp.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise RuntimeError(f"Executor container {info['container_name']} not ready")

    async def _touch_activity(self, user_id: str) -> None:
        await self.redis.set_json(
            f"parva:container:{user_id}:activity",
            {"last_active": datetime.utcnow().isoformat()},
            ttl=self.settings.executor_idle_timeout_seconds,
        )

    # ── Skill execution ───────────────────────────────────────────────

    async def execute_skill(
        self,
        user_id: str,
        execution_id: str,
        skill_name: str,
        skill_source: str,
        entrypoint: str,
        params: dict[str, Any],
        dependencies: list[str],
        files: dict[str, bytes] | None = None,
        timeout: int = 300,
    ) -> ExecutionProgress:
        """
        Execute a skill in the user's container.
        Returns final execution progress.
        """
        info = await self._get_or_create_container(user_id)
        base_url = f"http://{info['host']}:{info['port']}"

        # Send execution request to the executor sidecar
        payload = {
            "execution_id": execution_id,
            "skill_name": skill_name,
            "skill_source": skill_source,
            "entrypoint": entrypoint,
            "params": params,
            "dependencies": dependencies,
            "timeout": timeout,
        }

        # If there are files to inject, encode them as base64
        if files:
            import base64
            payload["files"] = {
                k: base64.b64encode(v).decode() for k, v in files.items()
            }

        try:
            resp = await self._http.post(
                f"{base_url}/execute",
                json=payload,
                timeout=timeout + 30,
            )
            result = resp.json()
            return ExecutionProgress(
                execution_id=execution_id,
                skill_name=skill_name,
                status=ExecutionStatus(result.get("status", "completed")),
                progress_pct=100.0 if result.get("status") == "completed" else 0,
                current_step=result.get("current_step", ""),
                logs=result.get("logs", ""),
                result=result.get("result"),
                error=result.get("error"),
                started_at=result.get("started_at"),
                finished_at=result.get("finished_at"),
            )
        except httpx.TimeoutException:
            return ExecutionProgress(
                execution_id=execution_id,
                skill_name=skill_name,
                status=ExecutionStatus.failed,
                error="Execution timed out",
            )
        except Exception as e:
            logger.exception("Skill execution failed")
            return ExecutionProgress(
                execution_id=execution_id,
                skill_name=skill_name,
                status=ExecutionStatus.failed,
                error=str(e),
            )

    # ── Container cleanup ──────────────────────────────────────────────

    async def cleanup_idle_containers(self) -> int:
        """Remove containers that have been idle too long. Run periodically."""
        cleaned = 0
        containers = self.docker.containers.list(
            filters={"label": "parva.role=executor"}
        )
        for container in containers:
            user_id = container.labels.get("parva.user")
            if not user_id:
                continue
            activity = await self.redis.get_json(
                f"parva:container:{user_id}:activity"
            )
            if activity is None:
                # TTL expired — container is idle
                logger.info(f"Reclaiming idle container for user {user_id}")
                container.stop(timeout=10)
                container.remove(force=True)
                await self.redis.delete(f"parva:container:{user_id}")
                cleaned += 1
        return cleaned

    async def destroy_user_container(self, user_id: str) -> None:
        """Forcefully remove a user's container."""
        name = self._container_name(user_id)
        try:
            container = self.docker.containers.get(name)
            container.stop(timeout=10)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        await self.redis.delete(f"parva:container:{user_id}")
