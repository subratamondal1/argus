"use client";

import { PenSquare, Trash2 } from "lucide-react";

import { cn } from "@/shared/lib/cn";

import { useChatStore } from "../store";

export function Sidebar() {
  const conversations = useChatStore((state) => state.conversations);
  const activeId = useChatStore((state) => state.activeId);
  const hydrated = useChatStore((state) => state.hydrated);
  const newConversation = useChatStore((state) => state.newConversation);
  const setActive = useChatStore((state) => state.setActive);
  const deleteConversation = useChatStore((state) => state.deleteConversation);

  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r border-foreground/10 bg-foreground/[0.02] md:flex">
      <div className="flex items-center gap-2 px-4 py-3.5">
        <span className="text-sm font-semibold tracking-tight">Argus</span>
        <span className="font-mono text-[9px] uppercase tracking-widest text-foreground/35">
          deep research
        </span>
      </div>
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={() => newConversation()}
          className="flex w-full items-center gap-2 rounded-md border border-foreground/15 bg-surface px-3 py-2 text-sm font-medium transition hover:border-accent/45"
        >
          <PenSquare className="h-4 w-4" /> New chat
        </button>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {hydrated &&
          conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={cn(
                "group flex items-center gap-1 rounded-md px-2 transition",
                conversation.id === activeId
                  ? "bg-foreground/[0.06]"
                  : "hover:bg-foreground/[0.03]",
              )}
            >
              <button
                type="button"
                onClick={() => setActive(conversation.id)}
                className="flex-1 truncate py-2 text-left text-sm text-foreground/75"
                title={conversation.title}
              >
                {conversation.title || "New chat"}
              </button>
              <button
                type="button"
                onClick={() => deleteConversation(conversation.id)}
                className="rounded p-1 opacity-0 transition group-hover:opacity-100"
                aria-label="Delete chat"
              >
                <Trash2 className="h-3.5 w-3.5 text-foreground/40 hover:text-red-500" />
              </button>
            </div>
          ))}
      </nav>
    </aside>
  );
}
