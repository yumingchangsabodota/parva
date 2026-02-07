"use client";

import { useState } from "react";
import { ArrowLeft, Cpu, Puzzle, Key, Activity } from "lucide-react";
import Link from "next/link";
import ModelsTab from "@/components/admin/ModelsTab";
import SkillsTab from "@/components/admin/SkillsTab";
import ProvidersTab from "@/components/admin/ProvidersTab";
import SystemTab from "@/components/admin/SystemTab";

const tabs = [
  { id: "models", label: "Models", icon: Cpu },
  { id: "skills", label: "Skills", icon: Puzzle },
  { id: "providers", label: "Providers", icon: Key },
  { id: "system", label: "System", icon: Activity },
] as const;

type TabId = (typeof tabs)[number]["id"];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<TabId>("models");

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* Header */}
      <div className="border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link
            href="/"
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-muted)]"
          >
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">Admin</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Platform configuration and monitoring
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 border-b border-[var(--border)] mb-6">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-parva-500 text-parva-500"
                    : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                }`}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {activeTab === "models" && <ModelsTab />}
        {activeTab === "skills" && <SkillsTab />}
        {activeTab === "providers" && <ProvidersTab />}
        {activeTab === "system" && <SystemTab />}
      </div>
    </div>
  );
}
