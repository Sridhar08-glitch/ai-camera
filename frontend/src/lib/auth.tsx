"use client";

// Auth context: holds the current user + access token in memory only.
// On mount it attempts a cookie-based silent refresh to restore a session
// across page reloads without persisting tokens in browser storage.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { login as apiLogin, logout as apiLogout, restoreSession } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    restoreSession()
      .then((u) => active && setUser(u))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function login(email: string, password: string) {
    const { user } = await apiLogin(email, password);
    setUser(user);
  }

  async function logout() {
    await apiLogout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
