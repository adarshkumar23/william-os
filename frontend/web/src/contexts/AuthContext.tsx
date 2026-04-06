import { createContext, useContext, useEffect, useMemo, useReducer } from "react";
import type { Dispatch, ReactNode } from "react";

import { api, clearAuthStorage, getAccessToken, saveTokens } from "../services/api";
import { AuthTokens, UserProfile } from "../types/api";

type AuthState = {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
};

type AuthAction =
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_USER"; payload: UserProfile | null }
  | { type: "LOGOUT" };

const initialState: AuthState = {
  user: null,
  isAuthenticated: Boolean(getAccessToken()),
  isLoading: true,
};

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, isLoading: action.payload };
    case "SET_USER":
      return {
        ...state,
        user: action.payload,
        isAuthenticated: Boolean(action.payload),
        isLoading: false,
      };
    case "LOGOUT":
      return { user: null, isAuthenticated: false, isLoading: false };
    default:
      return state;
  }
};

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    username: string;
    password: string;
    full_name: string;
    timezone?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<AuthTokens | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function hydrateCurrentUser(dispatch: Dispatch<AuthAction>) {
  try {
    const user = await api.auth.me();
    dispatch({ type: "SET_USER", payload: user });
  } catch {
    clearAuthStorage();
    dispatch({ type: "LOGOUT" });
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    if (!getAccessToken()) {
      dispatch({ type: "SET_LOADING", payload: false });
      return;
    }
    void hydrateCurrentUser(dispatch);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login: async (email: string, password: string) => {
        dispatch({ type: "SET_LOADING", payload: true });
        const tokens = await api.auth.login({
          email,
          password,
          device_name: "Web Dashboard",
          device_type: "web",
        });
        saveTokens(tokens);
        const me = await api.auth.me();
        dispatch({ type: "SET_USER", payload: me });
      },
      register: async ({ email, username, password, full_name, timezone }) => {
        dispatch({ type: "SET_LOADING", payload: true });
        await api.auth.register({ email, username, password, full_name, timezone });
        const tokens = await api.auth.login({
          email,
          password,
          device_name: "Web Dashboard",
          device_type: "web",
        });
        saveTokens(tokens);
        const me = await api.auth.me();
        dispatch({ type: "SET_USER", payload: me });
      },
      logout: async () => {
        try {
          await api.auth.logout();
        } catch {
          // no-op
        }
        clearAuthStorage();
        dispatch({ type: "LOGOUT" });
      },
      refreshToken: async () => {
        try {
          const tokens = await api.auth.refresh();
          saveTokens(tokens);
          return tokens;
        } catch {
          clearAuthStorage();
          dispatch({ type: "LOGOUT" });
          return null;
        }
      },
    }),
    [state],
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
