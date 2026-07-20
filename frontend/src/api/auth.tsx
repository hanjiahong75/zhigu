import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

interface User {
  id: number;
  username: string;
  nickname: string;
  avatar: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  updateUser: (u: Partial<User>) => void;
  refreshActivity: () => void;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("zhigu_auth");
    if (saved) {
      try {
        const { token: t, user: u, lastActivity } = JSON.parse(saved);
        const SESSION_MS = 8 * 60 * 60 * 1000; // 8 hours
        if (lastActivity && Date.now() - lastActivity > SESSION_MS) {
          localStorage.removeItem("zhigu_auth");
        } else {
          setToken(t);
          setUser(u);
          localStorage.setItem("zhigu_auth", JSON.stringify({ token: t, user: u, lastActivity: Date.now() }));
        }
      } catch { localStorage.removeItem("zhigu_auth"); }
    }
    setLoading(false);
  }, []);

  const login = (t: string, u: User) => {
    setToken(t);
    setUser(u);
    localStorage.setItem("zhigu_auth", JSON.stringify({ token: t, user: u, lastActivity: Date.now() }));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("zhigu_auth");
  };

  const refreshActivity = () => {
    const saved = localStorage.getItem("zhigu_auth");
    if (saved) {
      try {
        const d = JSON.parse(saved);
        d.lastActivity = Date.now();
        localStorage.setItem("zhigu_auth", JSON.stringify(d));
      } catch {}
    }
  };

  const updateUser = (u: Partial<User>) => {
    if (!user) return;
    const updated = { ...user, ...u };
    setUser(updated);
    localStorage.setItem("zhigu_auth", JSON.stringify({ token, user: updated, lastActivity: Date.now() }));
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, updateUser, refreshActivity }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export async function apiAuth(path: string, options: RequestInit = {}) {
  const saved = localStorage.getItem("zhigu_auth");
  const token = saved ? JSON.parse(saved).token : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`/api${path}`, { ...options, headers });
}
