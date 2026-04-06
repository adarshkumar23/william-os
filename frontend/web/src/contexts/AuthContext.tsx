import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, clearTokens, setTokens, UserProfile } from "../services/api";

type AuthContextValue = {
  currentUser: UserProfile | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    username: string;
    fullName: string;
    password: string;
  }) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = async () => {
    try {
      const profile = await api.auth.me();
      setCurrentUser(profile);
    } catch {
      setCurrentUser(null);
      clearTokens();
    }
  };

  const login = async (email: string, password: string) => {
    const tokens = await api.auth.login({
      email,
      password,
      device_name: "Web App",
      device_type: "web",
    });
    setTokens(tokens);
    await refreshMe();
  };

  const register = async (payload: {
    email: string;
    username: string;
    fullName: string;
    password: string;
  }) => {
    await api.auth.register({
      email: payload.email,
      username: payload.username,
      full_name: payload.fullName,
      password: payload.password,
    });
    await login(payload.email, payload.password);
  };

  const logout = () => {
    clearTokens();
    setCurrentUser(null);
  };

  useEffect(() => {
    const bootstrap = async () => {
      await refreshMe();
      setLoading(false);
    };
    void bootstrap();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ currentUser, loading, login, register, logout, refreshMe }),
    [currentUser, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
