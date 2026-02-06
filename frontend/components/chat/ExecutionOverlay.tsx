"use client";

import type { ExecutionProgress } from "@/types";
import { Loader2, CheckCircle, XCircle, Package } from "lucide-react";

interface Props {
  executions: ExecutionProgress[];
}

export default function ExecutionOverlay({ executions }: Props) {
  return (
    <div className="border-t border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="max-w-4xl mx-auto space-y-2">
        {executions.map((exec) => (
          <div
            key={exec.execution_id}
            className="flex items-center gap-3 text-sm"
          >
            <StatusIcon status={exec.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-[var(--text-primary)]">
                  {exec.skill_name}
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  {exec.current_step || exec.status}
                </span>
              </div>
              {/* Progress bar */}
              {exec.progress_pct > 0 && exec.progress_pct < 100 && (
                <div className="mt-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-parva-500 rounded-full transition-all duration-300"
                    style={{ width: `${exec.progress_pct}%` }}
                  />
                </div>
              )}
            </div>
            <span className="text-xs text-[var(--text-muted)] shrink-0">
              {exec.progress_pct > 0 ? `${Math.round(exec.progress_pct)}%` : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "queued":
      return <Package size={16} className="text-yellow-500" />;
    case "installing_deps":
      return <Loader2 size={16} className="text-blue-500 animate-spin" />;
    case "running":
      return <Loader2 size={16} className="text-parva-500 animate-spin" />;
    case "completed":
      return <CheckCircle size={16} className="text-green-500" />;
    case "failed":
      return <XCircle size={16} className="text-red-500" />;
    default:
      return <Loader2 size={16} className="text-gray-500 animate-spin" />;
  }
}
