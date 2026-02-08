"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getSkills, getModels, getModelPreferences, getThreads } from "@/lib/api";
import Sidebar from "@/components/common/Sidebar";
import ChatArea from "@/components/chat/ChatArea";
import NotificationToast from "@/components/notifications/NotificationToast";
import SettingsPanel from "@/components/common/SettingsPanel";

export default function Home() {
  const router = useRouter();
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const userId = useAppStore((s) => s.userId);
  const setSkills = useAppStore((s) => s.setSkills);
  const setModels = useAppStore((s) => s.setModels);
  const setChatModel = useAppStore((s) => s.setChatModel);
  const setImageModel = useAppStore((s) => s.setImageModel);
  const setThreads = useAppStore((s) => s.setThreads);
  const settingsOpen = useAppStore((s) => s.settingsOpen);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  // Initialize WebSocket connection
  useWebSocket();

  // Load initial data
  useEffect(() => {
    if (!isAuthenticated) return;

    const load = async () => {
      try {
        const [skills, models, prefs, threads] = await Promise.allSettled([
          getSkills(),
          getModels(),
          getModelPreferences(userId),
          getThreads(userId),
        ]);

        if (skills.status === "fulfilled") setSkills(skills.value);
        if (models.status === "fulfilled") setModels(models.value);
        if (prefs.status === "fulfilled") {
          if (prefs.value.chat_model) setChatModel(prefs.value.chat_model);
          if (prefs.value.image_model) setImageModel(prefs.value.image_model);
        }
        if (threads.status === "fulfilled") setThreads(threads.value);
      } catch (e) {
        console.error("Failed to load initial data:", e);
      }
    };
    load();
  }, [userId, isAuthenticated]);

  // Request notification permission
  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      if (Notification.permission === "default") {
        Notification.requestPermission();
      }
    }
  }, []);

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <ChatArea />
      {settingsOpen && <SettingsPanel />}
      <NotificationToast />
    </div>
  );
}
