"use client";

import { LogOut, User } from "lucide-react";
import { useState } from "react";

import { cn } from "@/shared/lib/cn";

import { signOut } from "../chat/sync";
import { AuthModal } from "./AuthModal";
import { useAuthStore } from "./store";

// The account section pinned to the bottom of the sidebar. Signed out: a "Sign in"
// affordance that opens the auth modal. Signed in: the email + an initial avatar,
// with a sign-out control. Collapses to a single avatar button on the icon rail.
export function Profile({ collapsed }: { collapsed: boolean }) {
  const [modalOpen, setModalOpen] = useState(false);
  const user = useAuthStore((state) => state.user);
  const initial: string = user ? user.email.charAt(0).toUpperCase() : "";

  return (
    <div
      className={cn("mt-auto w-full border-t border-foreground/10", collapsed ? "p-2" : "p-2.5")}
    >
      {user === null ? (
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          title="Sign in"
          className={cn(
            "flex items-center gap-2 rounded-md text-foreground/70 transition hover:bg-foreground/[0.06] hover:text-foreground",
            collapsed ? "justify-center p-2" : "w-full px-2.5 py-2",
          )}
        >
          <User className="h-4 w-4 shrink-0" />
          {!collapsed && <span className="text-sm">Sign in</span>}
        </button>
      ) : collapsed ? (
        <button
          type="button"
          onClick={signOut}
          title={`${user.email} — sign out`}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent transition hover:bg-accent/25"
        >
          {initial}
        </button>
      ) : (
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent">
            {initial}
          </span>
          <span
            className="min-w-0 flex-1 truncate text-[13px] text-foreground/75"
            title={user.email}
          >
            {user.email}
          </span>
          <button
            type="button"
            onClick={signOut}
            aria-label="Sign out"
            title="Sign out"
            className="shrink-0 rounded p-1.5 text-foreground/45 transition hover:bg-foreground/10 hover:text-foreground/90"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
      {modalOpen && <AuthModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
