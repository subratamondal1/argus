"use client";

import { Loader2, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { loadConversations } from "../chat/sync";
import { useAuthStore } from "./store";

// A sign-in / sign-up modal, portaled to <body> so it pins to the viewport.
export function AuthModal({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const busy = useAuthStore((state) => state.busy);
  const error = useAuthStore((state) => state.error);
  const login = useAuthStore((state) => state.login);
  const signup = useAuthStore((state) => state.signup);
  const clearError = useAuthStore((state) => state.clearError);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    const ok = await (mode === "login" ? login(email, password) : signup(email, password));
    if (ok) {
      await loadConversations();
      onClose();
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-sm rounded-lg border border-foreground/20 bg-surface p-6 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.8)]">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 rounded p-1 text-foreground/45 transition hover:bg-foreground/10 hover:text-foreground/90"
        >
          <X className="h-4 w-4" />
        </button>
        <h2 className="mb-1 font-sans text-lg font-semibold tracking-tight">
          {mode === "login" ? "Sign in to Argus" : "Create your Argus account"}
        </h2>
        <p className="mb-5 text-[13px] text-foreground/55">
          Your documents and research are isolated to your account.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              clearError();
            }}
            placeholder="you@example.com"
            autoComplete="email"
            className="w-full rounded-md border border-foreground/15 bg-transparent px-3 py-2 text-sm outline-none focus:border-accent/55"
          />
          <input
            type="password"
            required
            minLength={mode === "signup" ? 8 : undefined}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              clearError();
            }}
            placeholder={mode === "signup" ? "At least 8 characters" : "Password"}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className="w-full rounded-md border border-foreground/15 bg-transparent px-3 py-2 text-sm outline-none focus:border-accent/55"
          />
          {error !== null && <p className="text-[13px] text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            clearError();
          }}
          className="mt-4 w-full text-center text-[13px] text-foreground/55 transition hover:text-foreground/80"
        >
          {mode === "login" ? "No account? Create one" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>,
    document.body,
  );
}
