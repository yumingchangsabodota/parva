"use client";

import { useState, useEffect, useCallback } from "react";
import { getAdminSkills, deleteSkill } from "@/lib/admin-api";
import { importSkill } from "@/lib/api";
import { Trash2, Download, Loader2, Package, Tag } from "lucide-react";

interface SkillEntry {
  name: string;
  description: string;
  version: string;
  author: string;
  params: Array<{ name: string; type: string; description: string; required: boolean }>;
  tags: string[];
  builtin: boolean;
}

export default function SkillsTab() {
  const [skills, setSkills] = useState<SkillEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showImport, setShowImport] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAdminSkills();
      setSkills(data);
    } catch (e) {
      console.error("Failed to load skills:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSkills(); }, [loadSkills]);

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete skill "${name}"?`)) return;
    try {
      await deleteSkill(name);
      await loadSkills();
    } catch (e) {
      console.error("Failed to delete skill:", e);
    }
  };

  const handleImport = async () => {
    if (!importUrl) return;
    setImporting(true);
    try {
      await importSkill(importUrl, importName || undefined);
      setImportUrl("");
      setImportName("");
      setShowImport(false);
      await loadSkills();
    } catch (e) {
      console.error("Failed to import skill:", e);
    } finally {
      setImporting(false);
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
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Skills</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Manage agent skills — built-in and imported
          </p>
        </div>
        <button
          onClick={() => setShowImport(!showImport)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm"
        >
          <Download size={14} />
          Import Skill
        </button>
      </div>

      {/* Import form */}
      {showImport && (
        <div className="mb-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Git URL or tarball URL"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
            />
            <input
              type="text"
              placeholder="Custom name (optional)"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm"
            />
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button
              onClick={() => setShowImport(false)}
              className="px-3 py-1.5 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
            >
              Cancel
            </button>
            <button
              onClick={handleImport}
              disabled={importing || !importUrl}
              className="px-3 py-1.5 rounded-lg bg-parva-600 hover:bg-parva-700 text-white text-sm disabled:opacity-40"
            >
              {importing ? "Importing..." : "Import"}
            </button>
          </div>
        </div>
      )}

      {/* Skills list */}
      <div className="space-y-2">
        {skills.map((s) => (
          <div
            key={s.name}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Package size={16} className="text-parva-500" />
                  <span className="font-medium text-[var(--text-primary)]">{s.name}</span>
                  <span className="text-xs text-[var(--text-muted)]">v{s.version}</span>
                  {s.builtin && (
                    <span className="px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-xs text-[var(--text-muted)]">
                      built-in
                    </span>
                  )}
                </div>
                <p className="text-sm text-[var(--text-secondary)] mt-1">{s.description}</p>
                {s.tags.length > 0 && (
                  <div className="flex gap-1 mt-2">
                    {s.tags.map((t) => (
                      <span
                        key={t}
                        className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-xs text-[var(--text-muted)]"
                      >
                        <Tag size={10} />
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                {s.params.length > 0 && (
                  <div className="mt-2 text-xs text-[var(--text-muted)]">
                    Params: {s.params.map((p) => `${p.name} (${p.type})`).join(", ")}
                  </div>
                )}
              </div>
              {!s.builtin && (
                <button
                  onClick={() => handleDelete(s.name)}
                  className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-red-500"
                  title="Delete skill"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
