"use client";

import { useState, useEffect, useCallback } from "react";
import { getAdminModels, addModel, deleteModel, getDefaultModels, setDefaultModels } from "@/lib/admin-api";
import { Plus, Trash2, Star, Loader2 } from "lucide-react";

interface ModelEntry {
  model_name: string;
  model_info: Record<string, unknown>;
  litellm_params: Record<string, unknown>;
}

export default function ModelsTab() {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [defaults, setDefaults] = useState<{ chat_model: string; image_model: string }>({
    chat_model: "",
    image_model: "",
  });
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newModelName, setNewModelName] = useState("");
  const [newLitellmModel, setNewLitellmModel] = useState("");
  const [newApiKey, setNewApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [modelsData, defaultsData] = await Promise.all([
        getAdminModels(),
        getDefaultModels(),
      ]);
      setModels(modelsData.data || []);
      setDefaults(defaultsData);
    } catch (e) {
      console.error("Failed to load models:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAdd = async () => {
    if (!newModelName || !newLitellmModel) return;
    setSaving(true);
    try {
      await addModel({
        model_name: newModelName,
        litellm_model: newLitellmModel,
        api_key: newApiKey || undefined,
      });
      setNewModelName("");
      setNewLitellmModel("");
      setNewApiKey("");
      setShowAdd(false);
      await loadData();
    } catch (e) {
      console.error("Failed to add model:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (modelId: string) => {
    if (!confirm("Delete this model?")) return;
    try {
      await deleteModel(modelId);
      await loadData();
    } catch (e) {
      console.error("Failed to delete model:", e);
    }
  };

  const handleSetDefault = async (modelName: string, type: "chat" | "image") => {
    const updated = type === "chat"
      ? { ...defaults, chat_model: modelName }
      : { ...defaults, image_model: modelName };
    try {
      await setDefaultModels(updated);
      setDefaults(updated);
    } catch (e) {
      console.error("Failed to set default:", e);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-[var(--text-muted)]">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Models</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Manage LLM models available through LiteLLM proxy
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm"
        >
          <Plus size={14} />
          Add Model
        </button>
      </div>

      {/* Add model form */}
      {showAdd && (
        <div className="mb-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              type="text"
              placeholder="Display name (e.g. gpt-4o)"
              value={newModelName}
              onChange={(e) => setNewModelName(e.target.value)}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
            />
            <input
              type="text"
              placeholder="LiteLLM model (e.g. openai/gpt-4o)"
              value={newLitellmModel}
              onChange={(e) => setNewLitellmModel(e.target.value)}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
            />
            <input
              type="password"
              placeholder="API key (optional override)"
              value={newApiKey}
              onChange={(e) => setNewApiKey(e.target.value)}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
            />
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button
              onClick={() => setShowAdd(false)}
              className="px-3 py-1.5 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={saving || !newModelName || !newLitellmModel}
              className="px-3 py-1.5 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm disabled:opacity-40"
            >
              {saving ? "Adding..." : "Add"}
            </button>
          </div>
        </div>
      )}

      {/* Defaults */}
      <div className="mb-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm">
        <span className="text-[var(--text-muted)]">Defaults:</span>{" "}
        <span className="text-[var(--text-primary)] font-medium">Chat: {defaults.chat_model || "none"}</span>
        {" | "}
        <span className="text-[var(--text-primary)] font-medium">Image: {defaults.image_model || "none"}</span>
      </div>

      {/* Model list */}
      <div className="space-y-2">
        {models.length === 0 && (
          <div className="text-center text-[var(--text-muted)] py-8">No models configured</div>
        )}
        {models.map((m) => {
          const modelId = (m.model_info as any)?.id || m.model_name;
          const provider = String(m.litellm_params?.model || "").split("/")[0] || "unknown";
          const isDefaultChat = defaults.chat_model === m.model_name;
          const isDefaultImage = defaults.image_model === m.model_name;

          return (
            <div
              key={modelId}
              className="flex items-center justify-between p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-[var(--text-primary)]">{m.model_name}</span>
                  <span className="px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-xs text-[var(--text-muted)]">
                    {provider}
                  </span>
                  {isDefaultChat && (
                    <span className="px-2 py-0.5 rounded-full bg-parva-600/20 text-parva-500 text-xs">
                      Default Chat
                    </span>
                  )}
                  {isDefaultImage && (
                    <span className="px-2 py-0.5 rounded-full bg-parva-600/20 text-parva-500 text-xs">
                      Default Image
                    </span>
                  )}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-1">
                  {String(m.litellm_params?.model || "")}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleSetDefault(m.model_name, "chat")}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-parva-500"
                  title="Set as default chat model"
                >
                  <Star size={14} fill={isDefaultChat ? "currentColor" : "none"} />
                </button>
                <button
                  onClick={() => handleDelete(modelId)}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-red-500"
                  title="Delete model"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
