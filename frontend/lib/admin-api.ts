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

// ── Models ──────────────────────────────────────────────────────────

export async function getAdminModels() {
  return fetchJSON<{ data: Array<{ model_name: string; model_info: Record<string, unknown>; litellm_params: Record<string, unknown> }> }>(
    "/api/admin/models"
  );
}

export async function addModel(params: {
  model_name: string;
  litellm_model: string;
  api_key?: string;
}) {
  return fetchJSON("/api/admin/models", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function deleteModel(modelId: string) {
  return fetchJSON(`/api/admin/models/${modelId}`, { method: "DELETE" });
}

export async function getDefaultModels() {
  return fetchJSON<{ chat_model: string; image_model: string }>("/api/admin/models/defaults");
}

export async function setDefaultModels(params: { chat_model?: string; image_model?: string }) {
  return fetchJSON("/api/admin/models/defaults", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}

// ── Skills ──────────────────────────────────────────────────────────

export async function getAdminSkills() {
  return fetchJSON<Array<{
    name: string;
    description: string;
    version: string;
    author: string;
    params: Array<{ name: string; type: string; description: string; required: boolean }>;
    tags: string[];
    builtin: boolean;
  }>>("/api/admin/skills");
}

export async function deleteSkill(name: string) {
  return fetchJSON(`/api/admin/skills/${name}`, { method: "DELETE" });
}

// ── Providers ───────────────────────────────────────────────────────

export async function getProviders() {
  return fetchJSON<Array<{ provider: string; has_key: boolean; env_var: string }>>(
    "/api/admin/providers"
  );
}

export async function setProviderKey(provider: string, apiKey: string) {
  return fetchJSON("/api/admin/providers", {
    method: "PUT",
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
}

// ── System ──────────────────────────────────────────────────────────

export async function getSystemHealth() {
  return fetchJSON<{
    status: string;
    services: Record<string, { status: string; error?: string; [key: string]: unknown }>;
  }>("/api/admin/health");
}
