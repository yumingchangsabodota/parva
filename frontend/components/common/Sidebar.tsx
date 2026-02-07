"use client";

import { useAppStore } from "@/lib/store";
import { getThreadMessages } from "@/lib/api";
import Link from "next/link";
import {
  MessageSquare,
  Plus,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Puzzle,
  Bell,
  Shield,
} from "lucide-react";

export default function Sidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const toggleSettings = useAppStore((s) => s.toggleSettings);
  const threads = useAppStore((s) => s.threads);
  const currentThreadId = useAppStore((s) => s.currentThreadId);
  const setCurrentThread = useAppStore((s) => s.setCurrentThread);
  const setMessages = useAppStore((s) => s.setMessages);
  const userId = useAppStore((s) => s.userId);
  const notifications = useAppStore((s) => s.notifications);
  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleNewChat = () => {
    setCurrentThread(null);
    setMessages([]);
  };

  const handleSelectThread = async (threadId: string) => {
    setCurrentThread(threadId);
    try {
      const data = await getThreadMessages(threadId, userId);
      setMessages(
        data.messages.map((m: { role: string; content: string }) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }))
      );
    } catch (e) {
      console.error("Failed to load thread messages:", e);
    }
  };

  if (!sidebarOpen) {
    return (
      <div className="flex flex-col items-center py-4 px-2 border-r border-[var(--border)] bg-[var(--bg-secondary)]">
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          title="Open sidebar"
        >
          <PanelLeft size={20} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-72 flex flex-col border-r border-[var(--border)] bg-[var(--bg-secondary)] shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        <h1 className="text-lg font-bold text-parva-500">Parva</h1>
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          title="Close sidebar"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      {/* New Chat button */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          className="flex items-center gap-2 w-full px-4 py-2.5 rounded-lg bg-parva-600 hover:bg-parva-700 text-white transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-3">
        <div className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2 px-2">
          Recent Chats
        </div>
        {threads.length === 0 && (
          <div className="text-sm text-[var(--text-muted)] px-2 py-4 text-center">
            No conversations yet
          </div>
        )}
        {threads.map((t) => (
          <button
            key={t.thread_id}
            onClick={() => handleSelectThread(t.thread_id)}
            className={`flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors mb-1 ${
              currentThreadId === t.thread_id
                ? "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                : "hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
            }`}
          >
            <MessageSquare size={14} className="shrink-0" />
            <span className="truncate">
              {t.title || t.thread_id.slice(0, 8) + "..."}
            </span>
          </button>
        ))}
      </div>

      {/* Bottom actions */}
      <div className="border-t border-[var(--border)] p-3 space-y-1">
        <Link
          href="/admin"
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-secondary)]"
        >
          <Shield size={16} />
          Admin
        </Link>
        <button
          onClick={toggleSettings}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-secondary)]"
        >
          <Settings size={16} />
          Settings
          {unreadCount > 0 && (
            <span className="ml-auto bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
              {unreadCount}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
