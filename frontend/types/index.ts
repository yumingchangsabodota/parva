export interface ChatMessage {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  files?: FileRef[];
  metadata?: Record<string, unknown>;
  timestamp?: string;
}

export interface FileRef {
  key: string;
  filename: string;
  content_type: string;
  size: number;
}

export interface ThreadSummary {
  thread_id: string;
  title?: string;
  last_message?: string;
  updated_at: string;
}

export interface SkillParam {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: unknown;
}

export interface SkillInfo {
  name: string;
  description: string;
  version: string;
  author: string;
  params: SkillParam[];
  tags: string[];
  builtin: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  type: "chat" | "image";
}

export interface ExecutionProgress {
  execution_id: string;
  skill_name: string;
  status: "queued" | "installing_deps" | "running" | "completed" | "failed" | "cancelled";
  progress_pct: number;
  current_step: string;
  logs: string;
  result?: unknown;
  error?: string;
}

export interface WSEvent {
  type:
    | "token"
    | "message_done"
    | "execution_progress"
    | "execution_done"
    | "notification"
    | "error";
  thread_id?: string;
  data: Record<string, unknown>;
}

export interface Notification {
  id: string;
  message: string;
  type: string;
  timestamp: Date;
  read: boolean;
  threadId?: string;
}
