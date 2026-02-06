"""
Skill registry — manages built-in and user-imported skills.

Skills are stored as directories containing:
  - manifest.json  (SkillManifest)
  - main.py (or other entrypoint)
  - any other files the skill needs
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.models.schemas import SkillInfo, SkillManifest

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
BUILTINS_DIR = SKILLS_DIR / "builtins"
USER_SKILLS_DIR = Path("/var/parva/skills")  # persistent volume in prod


class SkillRegistry:
    """Registry of available skills (built-in + user-imported)."""

    def __init__(self) -> None:
        self._cache: dict[str, SkillManifest] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        if not BUILTINS_DIR.exists():
            return
        for skill_dir in BUILTINS_DIR.iterdir():
            if skill_dir.is_dir() and (skill_dir / "manifest.json").exists():
                self._load_skill(skill_dir, builtin=True)

    def _load_skill(self, skill_dir: Path, builtin: bool = False) -> SkillManifest | None:
        manifest_path = skill_dir / "manifest.json"
        if not manifest_path.exists():
            logger.warning(f"No manifest.json in {skill_dir}")
            return None
        try:
            data = json.loads(manifest_path.read_text())
            manifest = SkillManifest(**data)
            manifest_key = f"builtin:{manifest.name}" if builtin else manifest.name
            self._cache[manifest_key] = manifest
            return manifest
        except Exception as e:
            logger.error(f"Failed to load skill from {skill_dir}: {e}")
            return None

    def list_skills(self) -> list[SkillInfo]:
        skills: list[SkillInfo] = []
        # Built-ins
        for key, m in self._cache.items():
            skills.append(
                SkillInfo(
                    name=m.name,
                    description=m.description,
                    version=m.version,
                    author=m.author,
                    params=m.params,
                    tags=m.tags,
                    builtin=key.startswith("builtin:"),
                )
            )
        # User-imported
        if USER_SKILLS_DIR.exists():
            for skill_dir in USER_SKILLS_DIR.iterdir():
                if skill_dir.is_dir() and (skill_dir / "manifest.json").exists():
                    m = self._load_skill(skill_dir)
                    if m and m.name not in self._cache:
                        skills.append(
                            SkillInfo(
                                name=m.name,
                                description=m.description,
                                version=m.version,
                                author=m.author,
                                params=m.params,
                                tags=m.tags,
                                builtin=False,
                            )
                        )
        return skills

    def get_skill(self, name: str) -> SkillManifest | None:
        # Check builtin first, then user skills
        if f"builtin:{name}" in self._cache:
            return self._cache[f"builtin:{name}"]
        if name in self._cache:
            return self._cache[name]
        # Try loading from user skills dir
        user_dir = USER_SKILLS_DIR / name
        if user_dir.exists():
            return self._load_skill(user_dir)
        return None

    def get_skill_source(self, name: str) -> str | None:
        """Get the directory path containing the skill source files."""
        # Builtin
        builtin_path = BUILTINS_DIR / name
        if builtin_path.exists():
            return str(builtin_path)
        # User
        user_path = USER_SKILLS_DIR / name
        if user_path.exists():
            return str(user_path)
        return None

    def get_skill_source_archive(self, name: str) -> bytes | None:
        """Return a tar.gz of the skill directory for injection into containers."""
        source = self.get_skill_source(name)
        if not source:
            return None
        import tarfile
        import io
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(source, arcname=name)
        buf.seek(0)
        return buf.read()

    async def import_skill_from_url(self, url: str, name: str | None = None) -> SkillInfo:
        """Import a skill from a git repo URL or tarball URL."""
        import subprocess

        USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            if url.endswith(".git") or "github.com" in url or "gitlab.com" in url:
                subprocess.run(
                    ["git", "clone", "--depth=1", url, tmpdir],
                    check=True,
                    capture_output=True,
                )
            else:
                # Assume tarball
                import urllib.request
                archive_path = os.path.join(tmpdir, "skill.tar.gz")
                urllib.request.urlretrieve(url, archive_path)
                shutil.unpack_archive(archive_path, tmpdir)

            # Find manifest.json
            manifest_path = None
            for root, dirs, files in os.walk(tmpdir):
                if "manifest.json" in files:
                    manifest_path = Path(root)
                    break

            if not manifest_path:
                raise ValueError("No manifest.json found in imported skill")

            manifest = SkillManifest(
                **json.loads((manifest_path / "manifest.json").read_text())
            )
            skill_name = name or manifest.name
            dest = USER_SKILLS_DIR / skill_name

            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(manifest_path, dest)

            self._load_skill(dest)

            return SkillInfo(
                name=skill_name,
                description=manifest.description,
                version=manifest.version,
                author=manifest.author,
                params=manifest.params,
                tags=manifest.tags,
                builtin=False,
            )

    def build_skill_descriptions(self) -> str:
        """Build a text description of all available skills for the agent prompt."""
        skills = self.list_skills()
        if not skills:
            return "No skills available."
        lines = []
        for s in skills:
            params_desc = ""
            if s.params:
                params_desc = ", ".join(
                    f"{p.name}: {p.type}" + (" (required)" if p.required else "")
                    for p in s.params
                )
                params_desc = f" Params: [{params_desc}]"
            lines.append(f"- {s.name}: {s.description}{params_desc}")
        return "\n".join(lines)
