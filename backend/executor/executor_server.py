"""
Executor sidecar HTTP server.

Runs inside each user's container. Receives skill execution commands from
the Parva backend, installs dependencies, runs skills, and streams progress.

Supports: Python, TypeScript/JavaScript, and Bash skills.
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
import traceback
from datetime import datetime
from pathlib import Path

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor")

WORKSPACE = Path("/workspace")
SKILLS_DIR = WORKSPACE / ".skills"
PY_DEPS_CACHE = WORKSPACE / ".deps_installed"
NPM_DEPS_CACHE = WORKSPACE / ".npm_deps_installed"

# Track installed dependencies to avoid re-installing
_installed_py_deps: set[str] = set()
_installed_npm_deps: set[str] = set()


def _load_installed_deps():
    global _installed_py_deps, _installed_npm_deps
    if PY_DEPS_CACHE.exists():
        text = PY_DEPS_CACHE.read_text().strip()
        _installed_py_deps = set(text.split("\n")) if text else set()
    if NPM_DEPS_CACHE.exists():
        text = NPM_DEPS_CACHE.read_text().strip()
        _installed_npm_deps = set(text.split("\n")) if text else set()


def _save_installed_deps():
    PY_DEPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if _installed_py_deps:
        PY_DEPS_CACHE.write_text("\n".join(_installed_py_deps))
    if _installed_npm_deps:
        NPM_DEPS_CACHE.write_text("\n".join(_installed_npm_deps))


# ── Language-specific dependency installers ────────────────────────────

async def _install_python_deps(new_deps: list[str], log_fn) -> str | None:
    """Install Python deps via uv. Returns error string or None on success."""
    log_fn(f"Installing Python dependencies: {new_deps}")
    result = subprocess.run(
        ["uv", "pip", "install", "--system", "--quiet"] + new_deps,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return f"uv pip install failed: {result.stderr}"
    _installed_py_deps.update(new_deps)
    _save_installed_deps()
    log_fn("Python dependencies installed.")
    return None


async def _install_npm_deps(new_deps: list[str], skill_dir: Path, log_fn) -> str | None:
    """Install npm deps globally. Returns error string or None on success."""
    log_fn(f"Installing npm dependencies: {new_deps}")
    result = subprocess.run(
        ["npm", "install", "-g", "--silent"] + new_deps,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return f"npm install failed: {result.stderr}"
    _installed_npm_deps.update(new_deps)
    _save_installed_deps()
    log_fn("npm dependencies installed.")
    return None


# ── Language-specific command builders ─────────────────────────────────

def _build_command(language: str, script_path: Path) -> list[str]:
    """Return the command list to execute a skill based on its language."""
    lang = language.lower()
    ext = script_path.suffix.lower()

    if lang in ("python", "py") or ext == ".py":
        return [sys.executable, str(script_path)]

    if lang in ("typescript", "ts") or ext in (".ts", ".tsx"):
        return ["tsx", str(script_path)]

    if lang in ("javascript", "js", "node") or ext in (".js", ".mjs"):
        return ["node", str(script_path)]

    if lang in ("bash", "sh", "shell") or ext in (".sh", ".bash"):
        return ["bash", str(script_path)]

    # Fallback: try to run directly (for scripts with shebangs)
    return [str(script_path)]


def _get_dep_installer(language: str):
    """Return (installer_fn, cache_set) for the given language."""
    lang = language.lower()
    if lang in ("python", "py"):
        return _install_python_deps, _installed_py_deps
    if lang in ("typescript", "ts", "javascript", "js", "node"):
        return _install_npm_deps, _installed_npm_deps
    return None, set()


# ── Endpoints ──────────────────────────────────────────────────────────

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
        "language": "python",
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
    language = data.get("language", "python")
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
                "error": "Skill directory not found after extraction",
                "logs": "\n".join(logs_buffer),
            })

        # 2. Install dependencies (language-aware, only new ones)
        _load_installed_deps()
        installer_fn, dep_cache = _get_dep_installer(language)

        if dependencies and installer_fn:
            new_deps = [d for d in dependencies if d not in dep_cache]
            if new_deps:
                err = await installer_fn(new_deps, skill_dir, log)
                if err:
                    log(err)
                    return web.json_response({
                        "status": "failed",
                        "error": f"Dependency installation failed: {err}",
                        "logs": "\n".join(logs_buffer),
                        "started_at": started_at,
                        "finished_at": datetime.utcnow().isoformat(),
                    })

        # Also handle package.json if present for TS/JS skills
        pkg_json = skill_dir / "package.json"
        if pkg_json.exists() and language.lower() in ("typescript", "ts", "javascript", "js", "node"):
            log("Found package.json, running npm install...")
            result = subprocess.run(
                ["npm", "install", "--silent"],
                cwd=str(skill_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                log(f"npm install failed: {result.stderr}")
                # Non-fatal — global deps might be enough

        # 3. Write injected files to workspace
        if files:
            log(f"Injecting {len(files)} files...")
            files_dir = WORKSPACE / "files"
            files_dir.mkdir(exist_ok=True)
            for fname, fdata_b64 in files.items():
                fpath = files_dir / fname
                fpath.write_bytes(base64.b64decode(fdata_b64))

        # 4. Execute the skill
        script_path = skill_dir / entrypoint
        cmd = _build_command(language, script_path)
        log(f"Running [{language}]: {' '.join(cmd)}")

        # Make bash scripts executable
        if language.lower() in ("bash", "sh", "shell"):
            script_path.chmod(0o755)

        # Pass params as JSON via environment
        env = os.environ.copy()
        env["PARVA_PARAMS"] = json.dumps(params)
        env["PARVA_WORKSPACE"] = str(WORKSPACE)
        env["PARVA_EXECUTION_ID"] = execution_id
        env["PARVA_FILES_DIR"] = str(WORKSPACE / "files")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
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

        # 5. Parse result — skill should print JSON as last stdout line
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
