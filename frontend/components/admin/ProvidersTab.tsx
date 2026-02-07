"use client";

import { useState, useEffect, useCallback } from "react";
import { getProviders, setProviderKey } from "@/lib/admin-api";
import { Key, Check, Loader2, Eye, EyeOff } from "lucide-react";

interface Provider {
  provider: string;
  has_key: boolean;
  env_var: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google AI",
  azure: "Azure OpenAI",
};

export default function ProvidersTab() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadProviders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProviders();
      setProviders(data);
    } catch (e) {
      console.error("Failed to load providers:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadProviders(); }, [loadProviders]);

  const handleSave = async (provider: string) => {
    if (!keyInput) return;
    setSaving(true);
    try {
      await setProviderKey(provider, keyInput);
      setEditingProvider(null);
      setKeyInput("");
      setShowKey(false);
      await loadProviders();
    } catch (e) {
      console.error("Failed to save key:", e);
    } finally {
      setSaving(false);
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
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">LLM Providers</h2>
        <p className="text-sm text-[var(--text-muted)]">
          Set API keys for LLM providers. These are used by LiteLLM to route model requests.
        </p>
      </div>

      <div className="space-y-2">
        {providers.map((p) => (
          <div
            key={p.provider}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  p.has_key ? "bg-green-500/20 text-green-500" : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                }`}>
                  <Key size={18} />
                </div>
                <div>
                  <div className="font-medium text-[var(--text-primary)]">
                    {PROVIDER_LABELS[p.provider] || p.provider}
                  </div>
                  <div className="text-xs text-[var(--text-muted)]">{p.env_var}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {p.has_key && (
                  <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-green-500/20 text-green-500 text-xs">
                    <Check size={12} />
                    Configured
                  </span>
                )}
                <button
                  onClick={() => {
                    setEditingProvider(editingProvider === p.provider ? null : p.provider);
                    setKeyInput("");
                    setShowKey(false);
                  }}
                  className="px-3 py-1.5 rounded-lg text-sm bg-[var(--bg-tertiary)] hover:bg-[var(--border)] text-[var(--text-secondary)]"
                >
                  {p.has_key ? "Update Key" : "Set Key"}
                </button>
              </div>
            </div>

            {editingProvider === p.provider && (
              <div className="mt-3 flex gap-2">
                <div className="flex-1 relative">
                  <input
                    type={showKey ? "text" : "password"}
                    placeholder={`Enter ${PROVIDER_LABELS[p.provider] || p.provider} API key`}
                    value={keyInput}
                    onChange={(e) => setKeyInput(e.target.value)}
                    className="w-full px-3 py-2 pr-10 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
                  />
                  <button
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[var(--text-muted)]"
                  >
                    {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <button
                  onClick={() => handleSave(p.provider)}
                  disabled={saving || !keyInput}
                  className="px-4 py-2 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm disabled:opacity-40"
                >
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
