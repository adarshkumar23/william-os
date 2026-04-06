import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

export type APIEnvelope<T> = {
  ok: boolean;
  data: T;
  error: string | null;
  meta?: Record<string, unknown> | null;
};

export type UserProfile = {
  id: string;
  email: string;
  username: string;
  full_name: string;
  timezone: string;
  wake_time: string;
  sleep_time: string;
  preferences: Record<string, unknown>;
};

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

const ACCESS_KEY = "william_access_token";
const REFRESH_KEY = "william_refresh_token";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);

export const setTokens = (tokens: Partial<AuthTokens>) => {
  if (tokens.access_token) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
  }
  if (tokens.refresh_token) {
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  }
};

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
};

const apiClient = axios.create({ baseURL });

let refreshInFlight: Promise<string | null> | null = null;

const refreshAccessToken = async (): Promise<string | null> => {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  refreshInFlight = axios
    .post<APIEnvelope<AuthTokens>>(`${baseURL}/auth/refresh`, { refresh_token: refreshToken })
    .then((response) => {
      const tokens = response.data.data;
      if (!tokens?.access_token) {
        return null;
      }
      setTokens(tokens);
      return tokens.access_token;
    })
    .catch(() => {
      clearTokens();
      return null;
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
};

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        original.headers.Authorization = `Bearer ${refreshed}`;
        return apiClient(original);
      }
    }
    return Promise.reject(error);
  },
);

const unwrap = <T>(envelope: APIEnvelope<T>): T => envelope.data;

export const api = {
  auth: {
    register: (payload: {
      email: string;
      username: string;
      password: string;
      full_name: string;
    }) => apiClient.post<APIEnvelope<UserProfile>>("/auth/register", payload).then((r) => unwrap(r.data)),

    login: (payload: {
      email: string;
      password: string;
      device_name: string;
      device_type: string;
    }) => apiClient.post<APIEnvelope<AuthTokens>>("/auth/login", payload).then((r) => unwrap(r.data)),

    me: () => apiClient.get<APIEnvelope<UserProfile>>("/auth/me").then((r) => unwrap(r.data)),
  },

  schedule: {
    today: () => apiClient.get<APIEnvelope<any>>("/schedule/today").then((r) => unwrap(r.data)),
  },

  habits: {
    list: () => apiClient.get<APIEnvelope<any[]>>("/habits").then((r) => unwrap(r.data)),
    checkIn: (habitId: string) =>
      apiClient
        .post<APIEnvelope<any>>(`/habits/${habitId}/check-in`, {
          completed: true,
          skipped: false,
        })
        .then((r) => unwrap(r.data)),
    dailyCheckIns: (targetDate: string) =>
      apiClient.get<APIEnvelope<any[]>>(`/habits/check-ins/${targetDate}`).then((r) => unwrap(r.data)),
  },

  journal: {
    create: (payload: {
      content: string;
      passphrase: string;
      mood?: string;
      tags: string[];
    }) => apiClient.post<APIEnvelope<any>>("/journal", payload).then((r) => unwrap(r.data)),

    list: () => apiClient.get<APIEnvelope<any[]>>("/journal").then((r) => unwrap(r.data)),

    read: (entryId: string, passphrase: string) =>
      apiClient
        .post<APIEnvelope<any>>(`/journal/${entryId}/read`, { passphrase })
        .then((r) => unwrap(r.data)),
  },

  medicine: {
    list: () => apiClient.get<APIEnvelope<any[]>>("/medicine").then((r) => unwrap(r.data)),
    upcoming: () => apiClient.get<APIEnvelope<any[]>>("/medicine/upcoming").then((r) => unwrap(r.data)),
    adherence: () => apiClient.get<APIEnvelope<any>>("/medicine/adherence").then((r) => unwrap(r.data)),
    log: (medicineId: string, payload: { taken: boolean; skipped: boolean; skip_reason?: string }) =>
      apiClient.post<APIEnvelope<any>>(`/medicine/${medicineId}/log`, payload).then((r) => unwrap(r.data)),
  },

  study: {
    subjects: () => apiClient.get<APIEnvelope<any[]>>("/study/subjects").then((r) => unwrap(r.data)),
    progress: () => apiClient.get<APIEnvelope<any[]>>("/study/progress").then((r) => unwrap(r.data)),
    cardsDue: () => apiClient.get<APIEnvelope<any[]>>("/study/cards/due").then((r) => unwrap(r.data)),
    logSession: (payload: any) =>
      apiClient.post<APIEnvelope<any>>("/study/sessions", payload).then((r) => unwrap(r.data)),
  },

  fitness: {
    summary: (targetDate: string) =>
      apiClient.get<APIEnvelope<any>>(`/fitness/summary/${targetDate}`).then((r) => unwrap(r.data)),
    energy: (targetDate: string) =>
      apiClient.get<APIEnvelope<any>>(`/fitness/energy/${targetDate}`).then((r) => unwrap(r.data)),
    generateEnergy: (targetDate?: string) =>
      apiClient
        .post<APIEnvelope<any>>("/fitness/energy/generate", null, {
          params: targetDate ? { target_date: targetDate } : undefined,
        })
        .then((r) => unwrap(r.data)),
    workouts: () => apiClient.get<APIEnvelope<any[]>>("/fitness/workouts").then((r) => unwrap(r.data)),
    logWorkout: (payload: any) =>
      apiClient.post<APIEnvelope<any>>("/fitness/workouts", payload).then((r) => unwrap(r.data)),
    devices: () => apiClient.get<APIEnvelope<any[]>>("/fitness/devices").then((r) => unwrap(r.data)),
    addDevice: (payload: any) =>
      apiClient.post<APIEnvelope<any>>("/fitness/devices", payload).then((r) => unwrap(r.data)),
  },

  messaging: {
    telegramStatus: () =>
      apiClient.get<APIEnvelope<any>>("/messaging/telegram/status").then((r) => unwrap(r.data)),
    linkTelegram: (payload: { telegram_chat_id: number; telegram_username: string }) =>
      apiClient.post<APIEnvelope<any>>("/messaging/telegram/link", payload).then((r) => unwrap(r.data)),
  },
};
