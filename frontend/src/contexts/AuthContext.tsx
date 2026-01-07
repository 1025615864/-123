import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import api from "../api/client";
import type { User } from "../types";

function decodeJwtPayload(token: string): unknown {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const raw = parts[1];
    const base64 = raw.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function isJwtExpired(token: string): boolean | null {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload !== "object") return null;
  const exp = (payload as any).exp;
  if (typeof exp !== "number") return null;
  const now = Math.floor(Date.now() / 1000);
  return exp <= now;
}

function getInitialToken(): string | null {
  const raw = localStorage.getItem("token");
  if (!raw) return null;
  const token = raw.trim();
  if (!token || token === "null" || token === "undefined") {
    localStorage.removeItem("token");
    return null;
  }

  const payload = decodeJwtPayload(token);
  if (payload === null) {
    localStorage.removeItem("token");
    return null;
  }

  const expired = isJwtExpired(token);
  if (expired === true) {
    localStorage.removeItem("token");
    return null;
  }
  return token;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    agreeTerms: boolean,
    agreePrivacy: boolean,
    agreeAiDisclaimer: boolean
  ) => Promise<{ user: User; message?: string }>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => getInitialToken());

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  const refreshUser = async () => {
    if (!token) return;
    await fetchUser(token);
  };

  useEffect(() => {
    const handler = () => logout();
    window.addEventListener("auth:logout", handler);
    return () => window.removeEventListener("auth:logout", handler);
  }, []);

  useEffect(() => {
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      fetchUser(token);
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
  }, [token]);

  const fetchUser = async (activeToken: string) => {
    try {
      const response = await api.get("/user/me", {
        headers: {
          Authorization: `Bearer ${activeToken}`,
        },
      });
      if (localStorage.getItem("token") !== activeToken) {
        return;
      }
      setUser(response.data);
    } catch {
      if (localStorage.getItem("token") === activeToken) {
        logout();
      }
    }
  };

  const login = async (username: string, password: string) => {
    const response = await api.post("/user/login", { username, password });

    const { token, user: userData } = response.data;
    localStorage.setItem("token", token.access_token);
    setToken(token.access_token);
    setUser(userData);
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    agreeTerms: boolean,
    agreePrivacy: boolean,
    agreeAiDisclaimer: boolean
  ) => {
    const res = await api.post("/user/register", {
      username,
      email,
      password,
      agree_terms: agreeTerms,
      agree_privacy: agreePrivacy,
      agree_ai_disclaimer: agreeAiDisclaimer,
    });
    return res.data as { user: User; message?: string };
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        register,
        logout,
        refreshUser,
        isAuthenticated: !!token,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
