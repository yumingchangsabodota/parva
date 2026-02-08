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

export interface AuthUser {
  id: string;
  username: string;
  role: string;
  display_name: string;
}

interface AppState {
  // Auth
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;

  // User
  userId: string;
  setUserId: (id: string) => void;

  // Threads
  threads: ThreadSummary[];
  currentThreadId: string | null;
  setThreads: (threads: ThreadSummary[]) => void;
  setCurrentThread: (id: string | null) => void;

  // Messages (keyed by message ID)
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  upsertMessage: (message: ChatMessage) => void;
  mergeMessage: (id: string, fields: Partial<ChatMessage>) => void;

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

function getStoredAuth(): { token: string | null; user: AuthUser | null } {
  if (typeof window === "undefined") return { token: null, user: null };
  const token = localStorage.getItem("parva_token");
  const userStr = localStorage.getItem("parva_user");
  const user = userStr ? JSON.parse(userStr) : null;
  return { token, user };
}

export const useAppStore = create<AppState>((set, get) => {
  const stored = getStoredAuth();

  return {
    // Auth
    token: stored.token,
    user: stored.user,
    isAuthenticated: !!stored.token,
    setAuth: (token, user) => {
      localStorage.setItem("parva_token", token);
      localStorage.setItem("parva_user", JSON.stringify(user));
      localStorage.setItem("parva_user_id", user.id);
      set({ token, user, isAuthenticated: true, userId: user.id });
    },
    logout: () => {
      localStorage.removeItem("parva_token");
      localStorage.removeItem("parva_user");
      set({ token: null, user: null, isAuthenticated: false, threads: [], messages: [], currentThreadId: null });
    },

    // User
    userId: stored.user?.id || (typeof window !== "undefined" ? localStorage.getItem("parva_user_id") || crypto.randomUUID() : crypto.randomUUID()),
    setUserId: (id) => {
      if (typeof window !== "undefined") localStorage.setItem("parva_user_id", id);
      set({ userId: id });
    },

    // Threads
    threads: [],
    currentThreadId: null,
    setThreads: (threads) => set({ threads }),
    setCurrentThread: (id) => set({ currentThreadId: id }),

    // Messages (keyed by message ID)
    messages: [],
    setMessages: (messages) => set({ messages }),
    addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
    upsertMessage: (message) =>
      set((s) => {
        const idx = s.messages.findIndex((m) => m.id === message.id);
        if (idx >= 0) {
          // Merge: append content for streaming chunks, overwrite other fields
          const existing = s.messages[idx];
          const msgs = [...s.messages];
          msgs[idx] = {
            ...existing,
            ...message,
            content: existing.content + (message.content || ""),
          };
          return { messages: msgs };
        }
        return { messages: [...s.messages, message] };
      }),
    mergeMessage: (id, fields) =>
      set((s) => {
        const idx = s.messages.findIndex((m) => m.id === id);
        if (idx >= 0) {
          const msgs = [...s.messages];
          msgs[idx] = { ...msgs[idx], ...fields, content: msgs[idx].content };
          return { messages: msgs };
        }
        return s;
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
  };
});
