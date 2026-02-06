import { create } from "zustand";
import type {
  ChatMessage,
  FileRef,
  ThreadSummary,
  SkillInfo,
  ModelInfo,
  ExecutionProgress,
  Notification,
} from "@/types";

interface AppState {
  // User
  userId: string;
  setUserId: (id: string) => void;

  // Threads
  threads: ThreadSummary[];
  currentThreadId: string | null;
  setThreads: (threads: ThreadSummary[]) => void;
  setCurrentThread: (id: string | null) => void;

  // Messages
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  appendToLastMessage: (content: string) => void;

  // Streaming
  isStreaming: boolean;
  setIsStreaming: (s: boolean) => void;

  // Files
  uploadedFiles: FileRef[];
  addUploadedFile: (file: FileRef) => void;
  removeUploadedFile: (key: string) => void;
  clearUploadedFiles: () => void;

  // Skills
  skills: SkillInfo[];
  setSkills: (skills: SkillInfo[]) => void;

  // Models
  models: ModelInfo[];
  chatModel: string | null;
  imageModel: string | null;
  setModels: (models: ModelInfo[]) => void;
  setChatModel: (model: string | null) => void;
  setImageModel: (model: string | null) => void;

  // Executions
  activeExecutions: Map<string, ExecutionProgress>;
  updateExecution: (progress: ExecutionProgress) => void;
  removeExecution: (id: string) => void;

  // Notifications
  notifications: Notification[];
  addNotification: (n: Omit<Notification, "id" | "timestamp" | "read">) => void;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;

  // UI
  sidebarOpen: boolean;
  settingsOpen: boolean;
  toggleSidebar: () => void;
  toggleSettings: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // User
  userId: typeof window !== "undefined" ? localStorage.getItem("parva_user_id") || crypto.randomUUID() : crypto.randomUUID(),
  setUserId: (id) => {
    if (typeof window !== "undefined") localStorage.setItem("parva_user_id", id);
    set({ userId: id });
  },

  // Threads
  threads: [],
  currentThreadId: null,
  setThreads: (threads) => set({ threads }),
  setCurrentThread: (id) => set({ currentThreadId: id }),

  // Messages
  messages: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  appendToLastMessage: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length > 0 && msgs[msgs.length - 1].role === "assistant") {
        msgs[msgs.length - 1] = {
          ...msgs[msgs.length - 1],
          content: msgs[msgs.length - 1].content + content,
        };
      }
      return { messages: msgs };
    }),

  // Streaming
  isStreaming: false,
  setIsStreaming: (s) => set({ isStreaming: s }),

  // Files
  uploadedFiles: [],
  addUploadedFile: (file) =>
    set((s) => ({ uploadedFiles: [...s.uploadedFiles, file] })),
  removeUploadedFile: (key) =>
    set((s) => ({ uploadedFiles: s.uploadedFiles.filter((f) => f.key !== key) })),
  clearUploadedFiles: () => set({ uploadedFiles: [] }),

  // Skills
  skills: [],
  setSkills: (skills) => set({ skills }),

  // Models
  models: [],
  chatModel: null,
  imageModel: null,
  setModels: (models) => set({ models }),
  setChatModel: (model) => set({ chatModel: model }),
  setImageModel: (model) => set({ imageModel: model }),

  // Executions
  activeExecutions: new Map(),
  updateExecution: (progress) =>
    set((s) => {
      const map = new Map(s.activeExecutions);
      map.set(progress.execution_id, progress);
      return { activeExecutions: map };
    }),
  removeExecution: (id) =>
    set((s) => {
      const map = new Map(s.activeExecutions);
      map.delete(id);
      return { activeExecutions: map };
    }),

  // Notifications
  notifications: [],
  addNotification: (n) =>
    set((s) => ({
      notifications: [
        {
          ...n,
          id: crypto.randomUUID(),
          timestamp: new Date(),
          read: false,
        },
        ...s.notifications,
      ].slice(0, 50),
    })),
  markNotificationRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),
  clearNotifications: () => set({ notifications: [] }),

  // UI
  sidebarOpen: true,
  settingsOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleSettings: () => set((s) => ({ settingsOpen: !s.settingsOpen })),
}));
