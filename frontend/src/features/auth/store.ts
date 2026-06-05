"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { API_BASE, friendlyError, WITH_CREDENTIALS } from "@/shared/lib/api";

export interface AuthUser {
  id: string;
  email: string;
  tenant: string;
}

interface AuthState {
  // The JWT itself is NEVER held in JS — it lives in an httpOnly cookie the browser
  // sends automatically. `user` is the non-sensitive profile we show in the UI and
  // the "am I signed in?" signal; it's confirmed against the cookie via me().
  user: AuthUser | null;
  busy: boolean;
  error: string | null;
  signup: (email: string, password: string) => Promise<boolean>;
  login: (email: string, password: string) => Promise<boolean>;
  me: () => Promise<boolean>;
  setLoggedOut: () => void;
  clearError: () => void;
}

async function authenticate(path: string, email: string, password: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: WITH_CREDENTIALS, // store the Set-Cookie session the server returns
    body: JSON.stringify({ email, password }),
  });
  const body = (await response.json()) as { user?: AuthUser; error?: { message?: string } };
  if (!response.ok || !body.user) {
    throw new Error(body.error?.message ?? "authentication failed");
  }
  return body.user;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => {
      const run = async (path: string, email: string, password: string): Promise<boolean> => {
        set({ busy: true, error: null });
        try {
          const user = await authenticate(path, email, password);
          set({ user, busy: false });
          return true;
        } catch (caught) {
          set({ error: friendlyError(caught), busy: false });
          return false;
        }
      };
      return {
        user: null,
        busy: false,
        error: null,
        signup: (email, password) => run("/api/auth/signup", email, password),
        login: (email, password) => run("/api/auth/login", email, password),
        // Confirm the session cookie is still valid (e.g. on app mount / after a
        // reload). 401 -> the cookie expired or is gone: drop the cached user.
        me: async (): Promise<boolean> => {
          try {
            const response = await fetch(`${API_BASE}/api/auth/me`, {
              credentials: WITH_CREDENTIALS,
            });
            if (!response.ok) {
              set({ user: null });
              return false;
            }
            set({ user: (await response.json()) as AuthUser });
            return true;
          } catch {
            return get().user !== null; // network blip: keep cached state
          }
        },
        setLoggedOut: () => set({ user: null, error: null }),
        clearError: () => set({ error: null }),
      };
    },
    { name: "argus-auth", partialize: (state) => ({ user: state.user }) },
  ),
);
