"use client";

import { useState, useEffect, useCallback } from "react";
import { getSystemHealth } from "@/lib/admin-api";
import {
  Loader2,
  RefreshCw,
  Database,
  HardDrive,
  Cpu,
  Radio,
  Container,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from "lucide-react";

interface HealthData {
  status: string;
  services: Record<string, { status: string; error?: string; [key: string]: unknown }>;
}

const SERVICE_META: Record<string, { label: string; icon: typeof Database }> = {
  postgresql: { label: "PostgreSQL", icon: Database },
  redis: { label: "Redis", icon: Radio },
  minio: { label: "MinIO", icon: HardDrive },
  litellm: { label: "LiteLLM", icon: Cpu },
  executors: { label: "Executors", icon: Container },
};

function StatusIcon({ status }: { status: string }) {
  if (status === "healthy") return <CheckCircle2 size={18} className="text-green-500" />;
  if (status === "unhealthy") return <XCircle size={18} className="text-red-500" />;
  return <AlertCircle size={18} className="text-yellow-500" />;
}

export default function SystemTab() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadHealth = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getSystemHealth();
      setHealth(data);
    } catch (e) {
      console.error("Failed to load health:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadHealth(); }, [loadHealth]);

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
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">System Health</h2>
          <p className="text-sm text-[var(--text-muted)]">
            Monitor the status of all platform services
          </p>
        </div>
        <button
          onClick={() => loadHealth(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] border border-[var(--border)] text-sm text-[var(--text-secondary)]"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Overall status */}
      {health && (
        <div className={`mb-4 p-4 rounded-xl border ${
          health.status === "healthy"
            ? "border-green-500/30 bg-green-500/10"
            : "border-yellow-500/30 bg-yellow-500/10"
        }`}>
          <div className="flex items-center gap-2">
            <StatusIcon status={health.status} />
            <span className="font-medium text-[var(--text-primary)]">
              Platform is {health.status}
            </span>
          </div>
        </div>
      )}

      {/* Service cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {health && Object.entries(health.services).map(([name, info]) => {
          const meta = SERVICE_META[name] || { label: name, icon: Cpu };
          const Icon = meta.icon;

          return (
            <div
              key={name}
              className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Icon size={16} className="text-[var(--text-muted)]" />
                  <span className="font-medium text-[var(--text-primary)]">{meta.label}</span>
                </div>
                <StatusIcon status={info.status} />
              </div>

              {/* Extra info */}
              {info.error && (
                <div className="text-xs text-red-400 bg-red-500/10 rounded-lg p-2 mt-1 break-all">
                  {info.error}
                </div>
              )}
              {info.active_containers !== undefined && (
                <div className="text-xs text-[var(--text-muted)]">
                  Active containers: {String(info.active_containers)}
                </div>
              )}
              {info.buckets !== undefined && (
                <div className="text-xs text-[var(--text-muted)]">
                  Buckets: {String(info.buckets)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
