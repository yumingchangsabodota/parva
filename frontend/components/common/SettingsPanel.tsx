"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import {
  getSkills,
  getModels,
  importSkill,
  setModelPreferences,
} from "@/lib/api";
import {
  X,
  Cpu,
  Puzzle,
  Download,
  Check,
  Loader2,
  Image as ImageIcon,
  MessageSquare,
} from "lucide-react";
import type { SkillInfo, ModelInfo } from "@/types";

export default function SettingsPanel() {
  const toggleSettings = useAppStore((s) => s.toggleSettings);
  const userId = useAppStore((s) => s.userId);
  const [tab, setTab] = useState<"models" | "skills">("models");

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={toggleSettings}
      />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-lg bg-[var(--bg-primary)] border-l border-[var(--border)] h-full overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border)] sticky top-0 bg-[var(--bg-primary)] z-10">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button
            onClick={toggleSettings}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--border)]">
          <button
            onClick={() => setTab("models")}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              tab === "models"
                ? "text-parva-500 border-b-2 border-parva-500"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <Cpu size={16} />
              Models
            </div>
          </button>
          <button
            onClick={() => setTab("skills")}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              tab === "skills"
                ? "text-parva-500 border-b-2 border-parva-500"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <Puzzle size={16} />
              Skills
            </div>
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {tab === "models" ? (
            <ModelsTab userId={userId} />
          ) : (
            <SkillsTab userId={userId} />
          )}
        </div>
      </div>
    </div>
  );
}

function ModelsTab({ userId }: { userId: string }) {
  const models = useAppStore((s) => s.models);
  const chatModel = useAppStore((s) => s.chatModel);
  const imageModel = useAppStore((s) => s.imageModel);
  const setChatModel = useAppStore((s) => s.setChatModel);
  const setImageModel = useAppStore((s) => s.setImageModel);
  const setModels = useAppStore((s) => s.setModels);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getModels().then(setModels).catch(console.error);
  }, []);

  const chatModels = models.filter((m) => m.type === "chat");
  const imageModels = models.filter((m) => m.type === "image");

  const handleSave = async () => {
    setSaving(true);
    try {
      await setModelPreferences(userId, {
        chat_model: chatModel || undefined,
        image_model: imageModel || undefined,
      });
    } catch (e) {
      console.error("Failed to save preferences:", e);
    }
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      {/* Chat Model */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium mb-2 text-[var(--text-primary)]">
          <MessageSquare size={16} />
          Chat Model
        </label>
        <select
          value={chatModel || ""}
          onChange={(e) => setChatModel(e.target.value || null)}
          className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] outline-none focus:border-parva-500"
        >
          <option value="">Default</option>
          {chatModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>

      {/* Image Model */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium mb-2 text-[var(--text-primary)]">
          <ImageIcon size={16} />
          Image Model
        </label>
        <select
          value={imageModel || ""}
          onChange={(e) => setImageModel(e.target.value || null)}
          className="w-full px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] outline-none focus:border-parva-500"
        >
          <option value="">Default</option>
          {imageModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
      >
        {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
        Save Preferences
      </button>
    </div>
  );
}

function SkillsTab({ userId }: { userId: string }) {
  const skills = useAppStore((s) => s.skills);
  const setSkills = useAppStore((s) => s.setSkills);
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");

  useEffect(() => {
    getSkills().then(setSkills).catch(console.error);
  }, []);

  const handleImport = async () => {
    if (!importUrl.trim()) return;
    setImporting(true);
    setImportError("");
    try {
      await importSkill(importUrl.trim());
      const updated = await getSkills();
      setSkills(updated);
      setImportUrl("");
    } catch (e: any) {
      setImportError(e.message || "Import failed");
    }
    setImporting(false);
  };

  return (
    <div className="space-y-6">
      {/* Import skill */}
      <div>
        <label className="text-sm font-medium mb-2 block text-[var(--text-primary)]">
          Import External Skill
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            placeholder="Git repo URL or tarball URL"
            className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none focus:border-parva-500"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importUrl.trim()}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {importing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            Import
          </button>
        </div>
        {importError && (
          <p className="text-xs text-red-400 mt-1">{importError}</p>
        )}
      </div>

      {/* Skills list */}
      <div>
        <h3 className="text-sm font-medium mb-3 text-[var(--text-primary)]">
          Available Skills ({skills.length})
        </h3>
        <div className="space-y-2">
          {skills.map((skill) => (
            <div
              key={skill.name}
              className="p-3 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]"
            >
              <div className="flex items-center gap-2 mb-1">
                <Puzzle size={14} className="text-parva-500" />
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {skill.name}
                </span>
                {skill.builtin && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-parva-600/20 text-parva-400 font-medium">
                    BUILT-IN
                  </span>
                )}
                <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                  v{skill.version}
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] mb-2">
                {skill.description}
              </p>
              {skill.params.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {skill.params.map((p) => (
                    <span
                      key={p.name}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                    >
                      {p.name}
                      {p.required && "*"}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
