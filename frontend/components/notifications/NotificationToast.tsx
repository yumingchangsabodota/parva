"use client";

import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { X, CheckCircle, AlertCircle, Info, Bell } from "lucide-react";
import type { Notification } from "@/types";

export default function NotificationToast() {
  const notifications = useAppStore((s) => s.notifications);
  const markNotificationRead = useAppStore((s) => s.markNotificationRead);

  // Show only unread notifications, max 3
  const unread = notifications.filter((n) => !n.read).slice(0, 3);

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
      {unread.map((n) => (
        <Toast key={n.id} notification={n} onDismiss={() => markNotificationRead(n.id)} />
      ))}
    </div>
  );
}

function Toast({
  notification,
  onDismiss,
}: {
  notification: Notification;
  onDismiss: () => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Animate in
    requestAnimationFrame(() => setVisible(true));
    // Auto-dismiss after 5s
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 300);
    }, 5000);
    return () => clearTimeout(timer);
  }, []);

  const Icon =
    notification.type === "error"
      ? AlertCircle
      : notification.type === "execution_complete"
      ? CheckCircle
      : notification.type === "agent_done"
      ? Bell
      : Info;

  const iconColor =
    notification.type === "error"
      ? "text-red-400"
      : notification.type === "execution_complete"
      ? "text-green-400"
      : "text-parva-400";

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] shadow-lg transition-all duration-300 ${
        visible ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0"
      }`}
    >
      <Icon size={18} className={`${iconColor} shrink-0 mt-0.5`} />
      <p className="text-sm text-[var(--text-primary)] flex-1">
        {notification.message}
      </p>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(onDismiss, 300);
        }}
        className="p-0.5 rounded hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
