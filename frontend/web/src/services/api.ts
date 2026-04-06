import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

import {
  AnyRecord,
  ApiEnvelope,
  AuthTokens,
  DailyPlan,
  Decision,
  DecisionAnalysis,
  EnergyForecast,
  Habit,
  HabitCheckIn,
  LifeScore,
  LifeScoreHistoryPoint,
  JournalEntryDecrypted,
  JournalEntryMeta,
  Medicine,
  MedicineReminder,
  MockTest,
  NotificationItem,
  PortfolioSummary,
  RevisionCard,
  SleepRecommendation,
  SleepRecord,
  SleepStats,
  StudySession,
  Subject,
  Trade,
  UserProfile,
  VoiceHistoryItem,
  Workout,
} from "../types/api";

const ACCESS_KEY = "william_access_token";
const REFRESH_KEY = "william_refresh_token";

const resolveApiBaseUrl = () => {
  const envBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (envBase) {
    return envBase;
  }

  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return "http://localhost:8000/api/v1";
  }

  return "http://80.225.215.117:8000/api/v1";
};

const baseURL = resolveApiBaseUrl();

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);

export const saveTokens = (tokens: Partial<AuthTokens>) => {
  if (tokens.access_token) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
  }
  if (tokens.refresh_token) {
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  }
};

export const clearAuthStorage = () => {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
};

const apiClient = axios.create({
  baseURL,
  withCredentials: true,
  timeout: 30000,
});

const refreshClient = axios.create({
  baseURL,
  withCredentials: true,
  timeout: 30000,
});

let isRefreshing = false;
let requestQueue: Array<(token: string | null) => void> = [];

const flushQueue = (token: string | null) => {
  requestQueue.forEach((resolve) => resolve(token));
  requestQueue = [];
};

const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await refreshClient.post<ApiEnvelope<AuthTokens>>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    if (!response.data.ok) {
      return null;
    }

    const tokens = response.data.data;
    saveTokens(tokens);
    return tokens.access_token;
  } catch {
    return null;
  }
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
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (originalRequest.url?.includes("/auth/refresh")) {
      clearAuthStorage();
      window.location.assign("/login");
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        requestQueue.push((token) => {
          if (!token) {
            reject(error);
            return;
          }
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(apiClient(originalRequest));
        });
      });
    }

    isRefreshing = true;

    try {
      const newToken = await refreshAccessToken();
      flushQueue(newToken);

      if (!newToken) {
        clearAuthStorage();
        window.location.assign("/login");
        return Promise.reject(error);
      }

      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(originalRequest);
    } finally {
      isRefreshing = false;
    }
  },
);

const unwrap = <T>(response: ApiEnvelope<T>) => {
  if (!response.ok) {
    throw new Error(response.error || "Request failed");
  }
  return response.data;
};

const get = async <T>(url: string, params?: AnyRecord) => {
  const response = await apiClient.get<ApiEnvelope<T>>(url, { params });
  return unwrap(response.data);
};

const post = async <T>(url: string, payload?: AnyRecord) => {
  const response = await apiClient.post<ApiEnvelope<T>>(url, payload ?? {});
  return unwrap(response.data);
};

const patch = async <T>(url: string, payload?: AnyRecord) => {
  const response = await apiClient.patch<ApiEnvelope<T>>(url, payload ?? {});
  return unwrap(response.data);
};

const del = async <T>(url: string, payload?: AnyRecord) => {
  const response = await apiClient.delete<ApiEnvelope<T>>(url, payload ? { data: payload } : undefined);
  return unwrap(response.data);
};

export const api = {
  auth: {
    register: (payload: {
      email: string;
      username: string;
      password: string;
      full_name: string;
      timezone?: string;
    }) => post<UserProfile>("/auth/register", payload),
    login: (payload: {
      email: string;
      password: string;
      device_name?: string;
      device_type?: string;
    }) => post<AuthTokens>("/auth/login", payload),
    refresh: () => post<AuthTokens>("/auth/refresh", { refresh_token: getRefreshToken() }),
    logout: () => post<{ logged_out: boolean }>("/auth/logout"),
    me: () => get<UserProfile>("/auth/me"),
  },

  scheduler: {
    generate: (target_date: string, extra_context?: AnyRecord) =>
      post<DailyPlan>("/schedule/generate", { target_date, extra_context: extra_context ?? {} }),
    today: () => get<DailyPlan>("/schedule/today"),
    byDate: (planDate: string) => get<DailyPlan>(`/schedule/${planDate}`),
    addBlock: (planDate: string, payload: AnyRecord) => post<DailyPlan>(`/schedule/${planDate}/blocks`, payload),
    updateBlock: (blockId: string, payload: AnyRecord) => patch<DailyPlan>(`/schedule/blocks/${blockId}`, payload),
    startBlock: (blockId: string) => post<DailyPlan>(`/schedule/blocks/${blockId}/start`),
    reschedule: (planDate: string, payload: { reason: string; trigger?: string; new_constraints?: AnyRecord }) =>
      post<DailyPlan>(`/schedule/${planDate}/reschedule`, payload),
  },

  habits: {
    list: (params?: { active_only?: boolean; limit?: number; offset?: number }) => get<Habit[]>("/habits", params),
    create: (payload: AnyRecord) => post<Habit>("/habits", payload),
    update: (habitId: string, payload: AnyRecord) => patch<Habit>(`/habits/${habitId}`, payload),
    remove: (habitId: string) => del<{ deleted: boolean }>(`/habits/${habitId}`),
    checkIn: (habitId: string, payload: { check_date?: string; completed: boolean; skipped?: boolean }) =>
      post<HabitCheckIn>(`/habits/${habitId}/check-in`, payload),
    dailyCheckIns: (targetDate: string) => get<HabitCheckIn[]>(`/habits/check-ins/${targetDate}`),
    detectProcrastination: (payload: AnyRecord) => post<AnyRecord | null>("/habits/procrastination/detect", payload),
  },

  journal: {
    create: (payload: { content: string; passphrase: string; mood?: string; tags?: string[] }) =>
      post<JournalEntryMeta>("/journal", payload),
    list: (params?: AnyRecord) => get<JournalEntryMeta[]>("/journal", params),
    read: (entryId: string, passphrase: string) => post<JournalEntryDecrypted>(`/journal/${entryId}/read`, { passphrase }),
    summary: (entryId: string, passphrase: string) => post<JournalEntryDecrypted>(`/journal/${entryId}/summary`, { passphrase }),
    remove: (entryId: string) => del<{ deleted: boolean }>(`/journal/${entryId}`),
  },

  medicine: {
    list: (params?: { limit?: number; offset?: number }) => get<Medicine[]>("/medicine", params),
    create: (payload: AnyRecord) => post<Medicine>("/medicine", payload),
    update: (medicineId: string, payload: AnyRecord) => patch<Medicine>(`/medicine/${medicineId}`, payload),
    remove: (medicineId: string) => del<{ deleted: boolean }>(`/medicine/${medicineId}`),
    upcoming: (within_minutes = 30) => get<MedicineReminder[]>("/medicine/upcoming", { within_minutes }),
    adherence: (days = 30) => get<AnyRecord>("/medicine/adherence", { days }),
    refills: () => get<Medicine[]>("/medicine/refills"),
    log: (
      medicineId: string,
      payload: { taken: boolean; skipped?: boolean; skip_reason?: string | null },
      params?: { log_date?: string; scheduled_time?: string },
    ) =>
      post<AnyRecord>(
        `/medicine/${medicineId}/log${
          params
            ? `?${new URLSearchParams(
                Object.entries(params).filter(([, value]) => value) as Array<[string, string]>,
              ).toString()}`
            : ""
        }`,
        payload,
      ),
  },

  messaging: {
    history: (params?: { limit?: number; offset?: number }) => get<NotificationItem[]>("/messaging/history", params),
    send: (payload: AnyRecord) => post<NotificationItem>("/messaging/send", payload),
    telegramStatus: () => get<AnyRecord | null>("/messaging/telegram/status"),
    linkTelegram: (payload: AnyRecord) => post<AnyRecord>("/messaging/telegram/link", payload),
    unlinkTelegram: () => del<{ unlinked: boolean }>("/messaging/telegram/link"),
  },

  voice: {
    command: (payload: { text: string; journal_passphrase?: string }) => post<AnyRecord>("/voice/command", payload),
    history: (params?: { limit?: number; offset?: number }) => get<VoiceHistoryItem[]>("/voice/history", params),
  },

  study: {
    listSubjects: () => get<Subject[]>("/study/subjects"),
    createSubject: (payload: AnyRecord) => post<Subject>("/study/subjects", payload),
    listSessions: (params?: AnyRecord) => get<StudySession[]>("/study/sessions", params),
    createSession: (payload: AnyRecord) => post<StudySession>("/study/sessions", payload),
    listCards: (params?: AnyRecord) => get<RevisionCard[]>("/study/cards", params),
    createCard: (payload: AnyRecord) => post<RevisionCard>("/study/cards", payload),
    reviewCard: (cardId: string, quality: number) => post<RevisionCard>(`/study/cards/${cardId}/review`, { quality }),
    cardsDue: (for_date?: string) => get<RevisionCard[]>("/study/cards/due", { for_date }),
    listMocks: (params?: AnyRecord) => get<MockTest[]>("/study/mocks", params),
    createMock: (payload: AnyRecord) => post<MockTest>("/study/mocks", payload),
    progress: () => get<Array<Record<string, unknown>>>("/study/progress"),
    plan: (payload: { target_date: string; daily_hours: number }) => post<Array<Record<string, unknown>>>("/study/plan", payload),
    suggest: () => get<Record<string, unknown>>("/study/suggest"),
  },

  fitness: {
    summary: (targetDate: string) => get<Record<string, unknown>>(`/fitness/summary/${targetDate}`),
    listWorkouts: (days = 30) => get<Workout[]>("/fitness/workouts", { days }),
    logWorkout: (payload: AnyRecord) => post<Workout>("/fitness/workouts", payload),
    energyByDate: (targetDate: string) => get<EnergyForecast | null>(`/fitness/energy/${targetDate}`),
    generateEnergy: (target_date?: string) => post<EnergyForecast>(`/fitness/energy/generate${target_date ? `?target_date=${target_date}` : ""}`),
    suggestions: (target_date?: string) => get<string[]>("/fitness/energy/suggestions", { target_date }),
    metricHistory: (metricType: string, days = 30) => get<Array<Record<string, unknown>>>(`/fitness/metrics/${metricType}`, { days }),
  },

  trading: {
    watchlist: () => get<Array<Record<string, unknown>>>("/trading/watchlist"),
    addWatchlist: (payload: AnyRecord) => post<Record<string, unknown>>("/trading/watchlist", payload),
    removeWatchlist: (watchlistId: string) => del<{ deleted: boolean }>(`/trading/watchlist/${watchlistId}`),
    trades: (params?: AnyRecord) => get<Trade[]>("/trading/trades", params),
    logTrade: (payload: AnyRecord) => post<Trade>("/trading/trades", payload),
    portfolio: () => get<PortfolioSummary>("/trading/portfolio"),
    portfolioHistory: (days = 30) => get<Array<Record<string, unknown>>>("/trading/portfolio/history", { days }),
    analyze: (days = 90) => post<Record<string, unknown>>(`/trading/analyze?days=${days}`),
    alerts: () => get<Array<Record<string, unknown>>>("/trading/alerts"),
  },

  sleep: {
    log: (payload: AnyRecord) => post<SleepRecord>("/sleep/log", payload),
    history: (params?: AnyRecord) => get<SleepRecord[]>("/sleep/history", params),
    stats: () => get<SleepStats>("/sleep/stats"),
    debt: () => get<Record<string, unknown>>("/sleep/debt"),
    recommendationGenerate: (target_date?: string) =>
      post<SleepRecommendation>(`/sleep/recommendation/generate${target_date ? `?target_date=${target_date}` : ""}`),
    recommendationByDate: (targetDate: string) => get<SleepRecommendation>(`/sleep/recommendation/${targetDate}`),
    markRecommendationFollowed: (recommendationId: string, followed: boolean) =>
      patch<SleepRecommendation>(`/sleep/recommendation/${recommendationId}/followed`, { followed }),
    analyze: (days = 90) => post<Record<string, unknown>>(`/sleep/analyze?days=${days}`),
  },

  decisions: {
    list: (params?: AnyRecord) => get<Decision[]>("/decisions", params),
    create: (payload: AnyRecord) => post<Decision>("/decisions", payload),
    update: (decisionId: string, payload: AnyRecord) => patch<Decision>(`/decisions/${decisionId}`, payload),
    remove: (decisionId: string) => del<{ deleted: boolean }>(`/decisions/${decisionId}`),
    analyze: (decisionId: string) => post<DecisionAnalysis>(`/decisions/${decisionId}/analyze`),
    choose: (decisionId: string, payload: AnyRecord) => post<Decision>(`/decisions/${decisionId}/choose`, payload),
    outcome: (decisionId: string, payload: AnyRecord) => post<Decision>(`/decisions/${decisionId}/outcome`, payload),
    stats: () => get<Record<string, unknown>>("/decisions/stats"),
    templates: () => get<Array<Record<string, unknown>>>("/decisions/templates"),
  },

  email: {
    accounts: () => get<Array<Record<string, unknown>>>("/email/accounts"),
    connect: (payload: AnyRecord, oauth_token: string) =>
      post<Record<string, unknown>>(`/email/connect?oauth_token=${encodeURIComponent(oauth_token)}`, payload),
    disconnect: (accountId: string) => del<{ deleted: boolean }>(`/email/accounts/${accountId}`),
    sync: () => post<Record<string, unknown>>("/email/sync"),
    summary: () => get<Record<string, unknown> | null>("/email/summary"),
    briefing: () => get<Record<string, unknown>>("/email/briefing"),
  },

  intelligence: {
    lifeScore: () => get<LifeScore>("/intelligence/life-score"),
    lifeScoreHistory: (days = 30) => get<LifeScoreHistoryPoint[]>("/intelligence/life-score/history", { days }),
  },

  export: {
    summary: () => get<Record<string, unknown>>("/export/summary"),
    full: async () => {
      const response = await apiClient.post("/export/full", {}, { responseType: "blob" });
      return response.data as Blob;
    },
    journal: async (passphrase: string) => {
      const response = await apiClient.post("/export/journal", { passphrase }, { responseType: "blob" });
      return response.data as Blob;
    },
    lifetime: async (passphrase: string) => {
      const response = await apiClient.post("/export/lifetime", { passphrase }, { responseType: "blob" });
      return response.data as Blob;
    },
    deleteAccount: (password: string) => del<{ deleted: boolean }>("/export/account", { password }),
  },
};
