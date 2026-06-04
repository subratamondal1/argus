"use client";

import { PanelLeft, PanelLeftClose, PenSquare, Trash2, X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

import { Profile } from "../../auth/Profile";
import { useChatStore } from "../store";
import { openConversation, removeConversation } from "../sync";

// Static rail on md+; a slide-in drawer with backdrop on small screens. On
// desktop it collapses to a thin icon rail (expand + new chat) and expands back
// to the full list. Selecting a chat or starting a new one closes the mobile
// drawer so phone users always have a way back to a fresh chat and history.
export function Sidebar({
  open,
  onClose,
  collapsed,
  onToggleCollapse,
}: {
  open: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const conversations = useChatStore((state) => state.conversations);
  const activeId = useChatStore((state) => state.activeId);
  const hydrated = useChatStore((state) => state.hydrated);
  const newConversation = useChatStore((state) => state.newConversation);

  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-full w-72 max-w-[80vw] shrink-0 flex-col border-r border-foreground/10 bg-background transition-all duration-300 ease-out md:static md:z-auto md:bg-foreground/[0.02]",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          collapsed ? "md:w-14" : "md:w-64",
        )}
      >
        <div
          className={cn(
            "hidden flex-1 flex-col items-center gap-1 py-3",
            collapsed ? "md:flex" : "md:hidden",
          )}
        >
          <RailButton label="Expand sidebar" onClick={onToggleCollapse}>
            <PanelLeft className="h-4 w-4" />
          </RailButton>
          <RailButton label="New chat" onClick={() => newConversation()}>
            <PenSquare className="h-4 w-4" />
          </RailButton>
          <Profile collapsed />
        </div>

        <div className={cn("flex min-h-0 flex-1 flex-col", collapsed && "md:hidden")}>
          <div className="flex items-center gap-2 px-4 py-3.5">
            <span className="text-sm font-semibold tracking-tight">Argus</span>
            <span className="font-mono text-[9px] uppercase tracking-widest text-foreground/35">
              deep research
            </span>
            <div className="ml-auto flex items-center">
              <button
                type="button"
                onClick={onClose}
                aria-label="Close menu"
                className="rounded p-1 text-foreground/50 transition hover:bg-foreground/10 hover:text-foreground/80 md:hidden"
              >
                <X className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label="Collapse sidebar"
                className="hidden rounded p-1 text-foreground/50 transition hover:bg-foreground/10 hover:text-foreground/80 md:inline-flex"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </div>
          </div>
          <div className="px-3 pb-2">
            <button
              type="button"
              onClick={() => {
                newConversation();
                onClose();
              }}
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
                    onClick={() => {
                      void openConversation(conversation.id);
                      onClose();
                    }}
                    className="flex-1 truncate py-2 text-left text-sm text-foreground/75"
                    title={conversation.title}
                  >
                    {conversation.title || "New chat"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void removeConversation(conversation.id)}
                    className="rounded p-1 opacity-0 transition group-hover:opacity-100"
                    aria-label="Delete chat"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-foreground/40 hover:text-red-500" />
                  </button>
                </div>
              ))}
          </nav>
          <Profile collapsed={false} />
        </div>
      </aside>
    </>
  );
}

function RailButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded-md p-2 text-foreground/60 transition hover:bg-foreground/10 hover:text-foreground/90"
    >
      {children}
    </button>
  );
}
