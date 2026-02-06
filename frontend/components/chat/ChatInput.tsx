"use client";

import { useState, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { streamChat, uploadFiles } from "@/lib/api";
import {
  Send,
  Paperclip,
  X,
  FileText,
  Image as ImageIcon,
  Loader2,
  StopCircle,
} from "lucide-react";

export default function ChatInput() {
  const [input, setInput] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const userId = useAppStore((s) => s.userId);
  const currentThreadId = useAppStore((s) => s.currentThreadId);
  const setCurrentThread = useAppStore((s) => s.setCurrentThread);
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const uploadedFiles = useAppStore((s) => s.uploadedFiles);
  const addUploadedFile = useAppStore((s) => s.addUploadedFile);
  const removeUploadedFile = useAppStore((s) => s.removeUploadedFile);
  const clearUploadedFiles = useAppStore((s) => s.clearUploadedFiles);
  const chatModel = useAppStore((s) => s.chatModel);
  const imageModel = useAppStore((s) => s.imageModel);

  const handleSubmit = useCallback(async () => {
    const message = input.trim();
    if (!message || isStreaming) return;

    // Add user message to UI
    addMessage({ role: "user", content: message, files: uploadedFiles.length > 0 ? [...uploadedFiles] : undefined });
    setInput("");

    const fileKeys = uploadedFiles.map((f) => f.key);
    clearUploadedFiles();

    // Add empty assistant message for streaming
    addMessage({ role: "assistant", content: "" });
    setIsStreaming(true);

    try {
      let threadId = currentThreadId;

      for await (const event of streamChat({
        message,
        user_id: userId,
        thread_id: currentThreadId || undefined,
        files: fileKeys.length > 0 ? fileKeys : undefined,
        model: chatModel || undefined,
        image_model: imageModel || undefined,
      })) {
        switch (event.type) {
          case "thread_id":
            threadId = event.thread_id as string;
            if (!currentThreadId) {
              setCurrentThread(threadId);
            }
            break;
          case "token":
            appendToLastMessage(event.content as string);
            break;
          case "tool_start":
            appendToLastMessage(
              `\n\n> **Running skill:** ${event.tool}...\n\n`
            );
            break;
          case "tool_end":
            // Tool results are incorporated by the model
            break;
          case "error":
            appendToLastMessage(`\n\n**Error:** ${event.error}\n`);
            break;
          case "done":
            break;
        }
      }
    } catch (e) {
      console.error("Stream error:", e);
      appendToLastMessage("\n\n**Connection error. Please try again.**");
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, userId, currentThreadId, uploadedFiles, chatModel, imageModel]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const result = await uploadFiles(userId, files);
      for (const ref of result.files) {
        addUploadedFile(ref);
      }
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  return (
    <div className="border-t border-[var(--border)] bg-[var(--bg-primary)]">
      {/* Attached files */}
      {uploadedFiles.length > 0 && (
        <div className="flex gap-2 px-4 pt-3 flex-wrap max-w-4xl mx-auto w-full">
          {uploadedFiles.map((f) => (
            <div
              key={f.key}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-tertiary)] text-sm"
            >
              <FileText size={14} />
              <span className="truncate max-w-[150px]">{f.filename}</span>
              <button
                onClick={() => removeUploadedFile(f.key)}
                className="p-0.5 hover:bg-[var(--bg-secondary)] rounded"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="max-w-4xl mx-auto w-full px-4 py-3">
        <div className="flex items-end gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-3 focus-within:border-parva-500 transition-colors">
          {/* File upload button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)] shrink-0"
            title="Upload files"
          >
            {isUploading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Paperclip size={18} />
            )}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileUpload}
          />

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] max-h-[200px]"
          />

          {/* Send / Stop button */}
          {isStreaming ? (
            <button
              onClick={() => abortRef.current?.abort()}
              className="p-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white transition-colors shrink-0"
              title="Stop generating"
            >
              <StopCircle size={18} />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!input.trim()}
              className="p-1.5 rounded-lg bg-parva-600 hover:bg-parva-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
              title="Send message"
            >
              <Send size={18} />
            </button>
          )}
        </div>
        <div className="text-xs text-center text-[var(--text-muted)] mt-2">
          Parva can make mistakes. Skills run in isolated sandboxes.
        </div>
      </div>
    </div>
  );
}
