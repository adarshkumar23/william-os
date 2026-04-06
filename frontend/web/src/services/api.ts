import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import {
  cacheHabitsList,
  cacheMedicineList,
  cacheTodaySchedule,
  syncCriticalDataOnReconnect,
} from "./offlineStorage";

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
const OFFLINE_QUEUE_KEY = "william_offline_request_queue";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);

export const setTokens = (tokens: Partial<AuthTokens>) => {
  if (tokens.access_token) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
  }
};

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_KEY);
};

type OfflineQueuedRequest = {
  method: string;
  url: string;
  baseURL: string;
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  queuedAt: number;
};

const readOfflineQueue = (): OfflineQueuedRequest[] => {
  try {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as OfflineQueuedRequest[]) : [];
  } catch {
    return [];
  }
};

const writeOfflineQueue = (queue: OfflineQueuedRequest[]) => {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
};

const enqueueOfflineRequest = (config: InternalAxiosRequestConfig) => {
  const method = (config.method || "get").toUpperCase();
  const url = config.url || "";
  if (!url) {
    return;
  }

  const queue = readOfflineQueue();
  queue.push({
    method,
    url,
    baseURL: config.baseURL || baseURL,
    params: (config.params as Record<string, unknown>) || undefined,
    data: config.data,
    headers: {
      "Content-Type": "application/json",
      Authorization: config.headers?.Authorization as string,
    },
    queuedAt: Date.now(),
  });
  writeOfflineQueue(queue);
};

let replayInFlight = false;

const replayOfflineQueue = async () => {
  if (replayInFlight) {
    return;
  }

  const queue = readOfflineQueue();
  if (queue.length === 0) {
    return;
  }

  replayInFlight = true;
  const pending: OfflineQueuedRequest[] = [];

  for (const item of queue) {
    try {
      await axios.request({
        method: item.method,
        url: item.url,
        baseURL: item.baseURL,
        withCredentials: true,
        params: item.params,
        data: item.data,
        headers: {
          ...(item.headers || {}),
          "x-offline-replay": "true",
        },
      });
    } catch {
      pending.push(item);
    }
  }

  writeOfflineQueue(pending);
  replayInFlight = false;

  if (navigator.onLine) {
    try {
      await syncCriticalDataOnReconnect({
        fetchScheduleToday: async () => {
          const response = await apiClient.get<APIEnvelope<unknown>>("/schedule/today");
          return unwrap(response.data);
        },
        fetchHabitsList: async () => {
          const response = await apiClient.get<APIEnvelope<unknown[]>>("/habits");
          return unwrap(response.data);
        },
        fetchMedicineList: async () => {
          const response = await apiClient.get<APIEnvelope<unknown[]>>("/medicine");
          return unwrap(response.data);
        },
      });
    } catch {
      // Ignore reconnect-sync errors; queue replay will retry next online cycle.
    }
  }
};

if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    void replayOfflineQueue();
  });
}

const apiClient = axios.create({ baseURL, withCredentials: true });

let refreshInFlight: Promise<string | null> | null = null;

const refreshAccessToken = async (): Promise<string | null> => {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = axios
    .post<APIEnvelope<AuthTokens>>(`${baseURL}/auth/refresh`, {}, { withCredentials: true })
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

    const method = (original?.method || "get").toUpperCase();
    const isMutation = ["POST", "PATCH", "PUT", "DELETE"].includes(method);
    const isReplay = original?.headers?.["x-offline-replay"] === "true";
    if (!error.response && original && isMutation && !isReplay) {
      enqueueOfflineRequest(original);
      return Promise.resolve({
        status: 202,
        statusText: "Accepted",
        headers: {},
        config: original,
        data: {
          ok: true,
          data: { queued: true },
          error: null,
          meta: { offline: true },
        },
      } as any);
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

    logout: () => apiClient.post<APIEnvelope<{ logged_out: boolean }>>("/auth/logout").then((r) => unwrap(r.data)),

    me: () => apiClient.get<APIEnvelope<UserProfile>>("/auth/me").then((r) => unwrap(r.data)),
  },

  schedule: {
    today: () =>
      apiClient
        .get<APIEnvelope<any>>("/schedule/today")
        .then((r) => unwrap(r.data))
        .then(async (data) => {
          await cacheTodaySchedule(data);
          return data;
        }),
  },

  habits: {
    list: () =>
      apiClient
        .get<APIEnvelope<any[]>>("/habits")
        .then((r) => unwrap(r.data))
        .then(async (data) => {
          await cacheHabitsList(data);
          return data;
        }),
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
    list: () =>
      apiClient
        .get<APIEnvelope<any[]>>("/medicine")
        .then((r) => unwrap(r.data))
        .then(async (data) => {
          await cacheMedicineList(data);
          return data;
        }),
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
