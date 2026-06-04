"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import { API_BASE, friendlyError } from "@/shared/lib/api";

export interface AuthUser {
  id: string;
  email: string;
  tenant: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  busy: boolean;
  error: string | null;
  signup: (email: string, password: string) => Promise<boolean>;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
}

async function authenticate(
  path: string,
  email: string,
  password: string,
): Promise<{ token: string; user: AuthUser }> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = (await response.json()) as {
    token?: string;
    user?: AuthUser;
    error?: { message?: string };
  };
  if (!response.ok || !body.token || !body.user) {
    throw new Error(body.error?.message ?? "authentication failed");
  }
  return { token: body.token, user: body.user };
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => {
      const run = async (path: string, email: string, password: string): Promise<boolean> => {
        set({ busy: true, error: null });
        try {
          const { token, user } = await authenticate(path, email, password);
          set({ token, user, busy: false });
          return true;
        } catch (caught) {
          set({ error: friendlyError(caught), busy: false });
          return false;
        }
      };
      return {
        token: null,
        user: null,
        busy: false,
        error: null,
        signup: (email, password) => run("/api/auth/signup", email, password),
        login: (email, password) => run("/api/auth/login", email, password),
        logout: () => set({ token: null, user: null, error: null }),
        clearError: () => set({ error: null }),
      };
    },
    { name: "argus-auth", partialize: (state) => ({ token: state.token, user: state.user }) },
  ),
);

// Authorization header for API calls, when signed in. Spread into fetch headers.
export function authHeader(): Record<string, string> {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
