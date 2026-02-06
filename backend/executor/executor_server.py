"""
Executor sidecar HTTP server.

Runs inside each user's container. Receives skill execution commands from
the Parva backend, installs dependencies, runs skills, and streams progress.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from datetime import datetime
from http.server import HTTPServer
from pathlib import Path
from typing import Any

# Use built-in http.server for minimal dependencies
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor")

WORKSPACE = Path("/workspace")
SKILLS_DIR = WORKSPACE / ".skills"
DEPS_CACHE = WORKSPACE / ".deps_installed"

# Track installed dependencies to avoid re-installing
_installed_deps: set[str] = set()


def _load_installed_deps():
    global _installed_deps
    if DEPS_CACHE.exists():
        _installed_deps = set(DEPS_CACHE.read_text().strip().split("\n"))


def _save_installed_deps():
    DEPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DEPS_CACHE.write_text("\n".join(_installed_deps))


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def execute(request: web.Request) -> web.Response:
    """
    Execute a skill.

    Request JSON:
    {
        "execution_id": "...",
        "skill_name": "...",
        "skill_source": "<base64 tar.gz>",
        "entrypoint": "main.py",
        "params": {...},
        "dependencies": ["package1", "package2"],
        "files": {"filename": "<base64 data>", ...},
        "timeout": 300
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    execution_id = data.get("execution_id", "unknown")
    skill_name = data.get("skill_name", "unknown")
    skill_source_b64 = data.get("skill_source", "")
    entrypoint = data.get("entrypoint", "main.py")
    params = data.get("params", {})
    dependencies = data.get("dependencies", [])
    files = data.get("files", {})
    timeout = data.get("timeout", 300)

    started_at = datetime.utcnow().isoformat()
    logs_buffer = []

    def log(msg: str):
        logs_buffer.append(msg)
        logger.info(f"[{execution_id}] {msg}")

    try:
        # 1. Extract skill source
        log(f"Extracting skill '{skill_name}'...")
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skill_dir = SKILLS_DIR / skill_name

        if skill_source_b64:
            source_bytes = base64.b64decode(skill_source_b64)
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
            with tarfile.open(fileobj=io.BytesIO(source_bytes), mode="r:gz") as tar:
                tar.extractall(SKILLS_DIR)

        if not skill_dir.exists():
            return web.json_response({
                "status": "failed",
                "error": f"Skill directory not found after extraction",
                "logs": "\n".join(logs_buffer),
            })

        # 2. Install dependencies (only new ones)
        _load_installed_deps()
        new_deps = [d for d in dependencies if d not in _installed_deps]
        if new_deps:
            log(f"Installing dependencies: {new_deps}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + new_deps,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                log(f"pip install failed: {result.stderr}")
                return web.json_response({
                    "status": "failed",
                    "error": f"Dependency installation failed: {result.stderr}",
                    "logs": "\n".join(logs_buffer),
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat(),
                })
            _installed_deps.update(new_deps)
            _save_installed_deps()
            log("Dependencies installed.")

        # 3. Write injected files to workspace
        if files:
            log(f"Injecting {len(files)} files...")
            files_dir = WORKSPACE / "files"
            files_dir.mkdir(exist_ok=True)
            for fname, fdata_b64 in files.items():
                fpath = files_dir / fname
                fpath.write_bytes(base64.b64decode(fdata_b64))

        # 4. Execute the skill
        log(f"Running {entrypoint}...")
        script_path = skill_dir / entrypoint

        # Pass params as JSON via environment
        env = os.environ.copy()
        env["PARVA_PARAMS"] = json.dumps(params)
        env["PARVA_WORKSPACE"] = str(WORKSPACE)
        env["PARVA_EXECUTION_ID"] = execution_id
        env["PARVA_FILES_DIR"] = str(WORKSPACE / "files")

        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            cwd=str(skill_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return web.json_response({
                "status": "failed",
                "error": f"Execution timed out after {timeout}s",
                "logs": "\n".join(logs_buffer),
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
            })

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        logs_buffer.append(stdout_text)
        if stderr_text:
            logs_buffer.append(f"STDERR: {stderr_text}")

        if proc.returncode != 0:
            return web.json_response({
                "status": "failed",
                "error": f"Script exited with code {proc.returncode}",
                "logs": "\n".join(logs_buffer),
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
            })

        # 5. Parse result — the skill should print JSON to stdout as last line
        result = None
        for line in reversed(stdout_text.strip().split("\n")):
            try:
                result = json.loads(line)
                break
            except (json.JSONDecodeError, ValueError):
                continue

        if result is None:
            result = {"output": stdout_text.strip()}

        return web.json_response({
            "status": "completed",
            "result": result,
            "logs": "\n".join(logs_buffer),
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.exception("Execution error")
        return web.json_response({
            "status": "failed",
            "error": str(e),
            "logs": "\n".join(logs_buffer) + "\n" + traceback.format_exc(),
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
        })


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/execute", execute)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8100)
