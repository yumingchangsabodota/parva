"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { ChatMessage } from "@/types";
import { Bot, User, FileText, Copy, Check } from "lucide-react";
import { useState } from "react";

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  if (isTool) return null; // Hide tool messages from UI

  return (
    <div
      className={`flex gap-3 py-4 px-4 rounded-xl ${
        isUser ? "" : "bg-[var(--bg-secondary)]"
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          isUser
            ? "bg-gray-600 text-white"
            : "bg-parva-600 text-white"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-[var(--text-muted)] mb-1">
          {isUser ? "You" : "Parva"}
        </div>

        {/* File attachments */}
        {message.files && message.files.length > 0 && (
          <div className="flex gap-2 flex-wrap mb-2">
            {message.files.map((f) => (
              <div
                key={f.key}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--bg-tertiary)] text-xs"
              >
                <FileText size={12} />
                {f.filename}
              </div>
            ))}
          </div>
        )}

        {/* Message content */}
        {message.content ? (
          <div className="markdown-content text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const code = String(children).replace(/\n$/, "");

                  if (match) {
                    return (
                      <div className="relative group">
                        <CopyButton text={code} />
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                        >
                          {code}
                        </SyntaxHighlighter>
                      </div>
                    );
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
                img({ src, alt }) {
                  return (
                    <img
                      src={src}
                      alt={alt || ""}
                      className="max-w-full rounded-lg my-2 border border-[var(--border)]"
                      loading="lazy"
                    />
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        ) : (
          <span className="cursor-blink text-sm" />
        )}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
      title="Copy code"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}
