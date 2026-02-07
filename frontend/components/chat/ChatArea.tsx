"use client";

import { useRef, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import ExecutionOverlay from "./ExecutionOverlay";
import { Bot } from "lucide-react";

export default function ChatArea() {
  const messages = useAppStore((s) => s.messages);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const activeExecutions = useAppStore((s) => s.activeExecutions);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const runningExecutions = Array.from(activeExecutions.values()).filter(
    (e) => e.status === "running" || e.status === "installing_deps" || e.status === "queued"
  );

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <div className="max-w-4xl mx-auto px-4 py-6 space-y-1">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isStreaming && (
              <div className="flex items-center gap-2 text-[var(--text-muted)] text-sm py-2 px-4">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-parva-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-parva-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-parva-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Active executions overlay */}
      {runningExecutions.length > 0 && (
        <ExecutionOverlay executions={runningExecutions} />
      )}

      {/* Input area */}
      <ChatInput />
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 rounded-2xl bg-parva-600 flex items-center justify-center mb-6">
        <Bot size={32} className="text-white" />
      </div>
      <h2 className="text-2xl font-bold mb-2 text-[var(--text-primary)]">
        Welcome to Parva
      </h2>
      <p className="text-[var(--text-secondary)] max-w-md mb-8">
        Your AI agent with isolated skill execution. Upload files, generate
        images, run code, and more — all in sandboxed environments.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
        {[
          { title: "Run Python code", desc: "Execute scripts in a sandbox" },
          { title: "Analyze files", desc: "Upload and process any file type" },
          { title: "Generate images", desc: "Create images from descriptions" },
          { title: "Scrape websites", desc: "Fetch and extract web content" },
        ].map((item) => (
          <div
            key={item.title}
            className="p-4 rounded-xl border border-[var(--border)] hover:border-parva-400 hover:bg-[var(--bg-secondary)] transition-colors cursor-pointer text-left"
          >
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {item.title}
            </div>
            <div className="text-xs text-[var(--text-muted)] mt-1">
              {item.desc}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
