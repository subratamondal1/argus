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
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r border-zinc-200/60 bg-zinc-50/60 dark:border-zinc-800/60 dark:bg-zinc-900/30 md:flex">
      <div className="flex items-center gap-2 px-4 py-3.5">
        <span className="text-sm font-semibold tracking-tight">Argus</span>
      </div>
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={() => newConversation()}
          className="flex w-full items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium transition hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
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
                "group flex items-center gap-1 rounded-lg px-2 transition",
                conversation.id === activeId
                  ? "bg-zinc-200/70 dark:bg-zinc-800"
                  : "hover:bg-zinc-100 dark:hover:bg-zinc-800/50",
              )}
            >
              <button
                type="button"
                onClick={() => setActive(conversation.id)}
                className="flex-1 truncate py-2 text-left text-sm text-zinc-700 dark:text-zinc-200"
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
                <Trash2 className="h-3.5 w-3.5 text-zinc-400 hover:text-red-500" />
              </button>
            </div>
          ))}
      </nav>
    </aside>
  );
}
