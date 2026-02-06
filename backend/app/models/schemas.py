from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Users ──────────────────────────────────────────────────────────────
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Chat ───────────────────────────────────────────────────────────────
class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    files: list[FileRef] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    user_id: str
    files: list[str] | None = None  # MinIO object keys
    model: str | None = None
    image_model: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    message: ChatMessage
    execution_id: str | None = None


class ThreadSummary(BaseModel):
    thread_id: str
    title: str | None = None
    last_message: str | None = None
    updated_at: datetime


# ── Files ──────────────────────────────────────────────────────────────
class FileRef(BaseModel):
    key: str  # MinIO object key
    filename: str
    content_type: str
    size: int


class FileUploadResponse(BaseModel):
    files: list[FileRef]


# ── Skills ─────────────────────────────────────────────────────────────
class SkillParam(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


class SkillManifest(BaseModel):
    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    entrypoint: str = "main.py"  # script to run
    language: str = "python"
    dependencies: list[str] = Field(default_factory=list)  # pip packages
    params: list[SkillParam] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300


class SkillInfo(BaseModel):
    name: str
    description: str
    version: str
    author: str
    params: list[SkillParam]
    tags: list[str]
    builtin: bool = False


class SkillImportRequest(BaseModel):
    """Import a skill from a URL (git repo or tarball)."""
    url: str
    name: str | None = None  # override name


# ── Execution ──────────────────────────────────────────────────────────
class ExecutionStatus(str, Enum):
    queued = "queued"
    installing_deps = "installing_deps"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ExecutionProgress(BaseModel):
    execution_id: str
    skill_name: str
    status: ExecutionStatus
    progress_pct: float = 0.0  # 0-100
    current_step: str = ""
    logs: str = ""
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExecutionRequest(BaseModel):
    skill_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    user_id: str


# ── Models ─────────────────────────────────────────────────────────────
class ModelInfo(BaseModel):
    id: str
    name: str
    type: str  # "chat" or "image"


class UserModelPrefs(BaseModel):
    chat_model: str | None = None
    image_model: str | None = None


# ── WebSocket events ──────────────────────────────────────────────────
class WSEventType(str, Enum):
    # Streaming
    token = "token"
    message_done = "message_done"
    # Execution
    execution_progress = "execution_progress"
    execution_done = "execution_done"
    # Notifications
    notification = "notification"
    error = "error"


class WSEvent(BaseModel):
    type: WSEventType
    thread_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
