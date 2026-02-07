const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
}

// ── Chat ─────────────────────────────────────────────────────────────

export async function sendMessage(params: {
  message: string;
  user_id: string;
  thread_id?: string;
  files?: string[];
  model?: string;
  image_model?: string;
}) {
  return fetchJSON("/api/chat", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

import type { StreamEvent } from "@/types";

export async function* streamChat(params: {
  message: string;
  user_id: string;
  thread_id?: string;
  files?: string[];
  model?: string;
  image_model?: string;
}): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    throw new Error(`Stream error ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          yield data;
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}

// ── Threads ──────────────────────────────────────────────────────────

export async function getThreads(userId: string) {
  return fetchJSON<Array<{ thread_id: string; title?: string; updated_at: string }>>(
    `/api/threads?user_id=${userId}`
  );
}

export async function getThreadMessages(threadId: string, userId: string) {
  return fetchJSON<{ messages: Array<import("@/types").ChatMessage> }>(
    `/api/threads/${threadId}/messages?user_id=${userId}`
  );
}

// ── Files ────────────────────────────────────────────────────────────

export async function uploadFiles(userId: string, files: File[]) {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const res = await fetch(`${API_URL}/api/files/upload?user_id=${userId}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function getFileUrl(fileKey: string) {
  return fetchJSON<{ url: string }>(`/api/files/${fileKey}/url`);
}

// ── Skills ───────────────────────────────────────────────────────────

export async function getSkills() {
  return fetchJSON<Array<{
    name: string;
    description: string;
    version: string;
    params: Array<{ name: string; type: string; description: string; required: boolean }>;
    tags: string[];
    builtin: boolean;
  }>>("/api/skills");
}

export async function importSkill(url: string, name?: string) {
  return fetchJSON("/api/skills/import", {
    method: "POST",
    body: JSON.stringify({ url, name }),
  });
}

// ── Models ───────────────────────────────────────────────────────────

export async function getModels() {
  return fetchJSON<Array<{ id: string; name: string; type: string }>>("/api/models");
}

export async function getModelPreferences(userId: string) {
  return fetchJSON<{ chat_model?: string; image_model?: string }>(
    `/api/models/preferences?user_id=${userId}`
  );
}

export async function setModelPreferences(
  userId: string,
  prefs: { chat_model?: string; image_model?: string }
) {
  return fetchJSON(`/api/models/preferences?user_id=${userId}`, {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
}
