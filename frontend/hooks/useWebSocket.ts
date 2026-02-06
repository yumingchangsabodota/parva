"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import type { WSEvent, ExecutionProgress } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const userId = useAppStore((s) => s.userId);
  const addNotification = useAppStore((s) => s.addNotification);
  const updateExecution = useAppStore((s) => s.updateExecution);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_URL}/ws/${userId}`);

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const data: WSEvent = JSON.parse(event.data);
        handleEvent(data);
      } catch (e) {
        console.error("Failed to parse WS message", e);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected, reconnecting...");
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = (e) => {
      console.error("WebSocket error", e);
    };

    wsRef.current = ws;
  }, [userId]);

  const handleEvent = useCallback(
    (event: WSEvent) => {
      switch (event.type) {
        case "execution_progress":
          updateExecution(event.data as unknown as ExecutionProgress);
          break;

        case "execution_done":
          addNotification({
            message: `Skill "${event.data.skill_name}" ${event.data.success ? "completed" : "failed"}`,
            type: "execution_complete",
            threadId: event.thread_id,
          });
          // Play notification sound (optional)
          if (typeof window !== "undefined" && Notification.permission === "granted") {
            new Notification("Parva", {
              body: `Skill "${event.data.skill_name}" finished`,
            });
          }
          break;

        case "notification":
          addNotification({
            message: event.data.message as string,
            type: event.data.notification_type as string,
            threadId: event.thread_id,
          });
          break;

        case "error":
          addNotification({
            message: event.data.error as string || "An error occurred",
            type: "error",
          });
          break;
      }
    },
    [addNotification, updateExecution]
  );

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return wsRef;
}
