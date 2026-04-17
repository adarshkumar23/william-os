import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

import {
  AnyRecord,
  AdminStats,
  AdminUser,
  ApiEnvelope,
  ActivityFeedItem,
  AgentRunAllResult,
  AgentRecommendationLog,
  AgentStatus,
  AuthTokens,
  AskTimelineResponse,
  BurnoutInterventionPayload,
  BurnoutScorePayload,
  CalendarEvent,
  CalendarSyncConflict,
  NativeCalendarEventPatch,
  NativeCalendarEventPayload,
  OnboardingCompleteResponse,
  OnboardingCompletePayload,
  OnboardingStatus,
  CalendarTodayResponse,
  CursorPage,
  GamificationProfile,
  GamificationRecord,
  GamificationXPEvent,
  MorningBriefing,
  MorningBriefingSendResult,
  DailyPlan,
  Decision,
  DecisionAnalysis,
  EnergyForecast,
  LoginHistoryItem,
  SecretMetadata,
  SessionDevice,
  TotpSetupPayload,
  Habit,
  HabitCheckIn,
  LifeScore,
  LifeScoreHistoryPoint,
  TimelineEvent,
  JournalEntryDecrypted,
  JournalDraft,
  JournalEntryMeta,
  JournalUnlockResponse,
  Medicine,
  MedicineReminder,
  MockTest,
  NotificationItem,
  PortfolioSummary,
  PredictiveWarning,
  RuleEvaluationResult,
  RuleTemplate,
  RevisionCard,
  SleepRecommendation,
  SleepRecord,
  SleepStats,
  StudySession,
  StudyDashboard,
  Subject,
  Trade,
  UserRule,
  UserProfile,
  VoiceHistoryItem,
  WeeklyReview,
  Workout,
  ChatSession,
  ChatSessionListItem,
  ChatMessage,
  ChatStreamEvent,
} from "../types/api";
import { recordApiError, recordRefreshTokenFailure } from "../observability/client";

const baseURL = "/api/v1";

// C10 fix: access token in memory only; refresh token lives in httpOnly cookie.
let _accessToken: string | null = null;

export const getAccessToken = () => _accessToken;
// Refresh token is in httpOnly cookie — not accessible from JS; kept for API shape compat.
export const getRefreshToken = (): string | null => null;

export const saveTokens = (tokens: Partial<AuthTokens>) => {
  if (tokens.access_token) {
    _accessToken = tokens.access_token;
  }
};

export const clearAuthStorage = () => {
  _accessToken = null;
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
  try {
    const response = await refreshClient.post<ApiEnvelope<AuthTokens>>("/auth/refresh", {});
    if (!response.data.ok) {
      return null;
    }
    const tokens = response.data.data;
    saveTokens(tokens);
    return tokens.access_token;
  } catch {
    recordRefreshTokenFailure(window.location.pathname);
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
    const statusCode = error.response?.status ?? 0;

    if (originalRequest?.url && !originalRequest.url.includes("/auth/refresh")) {
      recordApiError(window.location.pathname, originalRequest.url, statusCode);
    }

    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (originalRequest.url?.includes("/auth/refresh")) {
      recordRefreshTokenFailure(window.location.pathname);
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

const normalizeParams = (params?: AnyRecord): AnyRecord | undefined => {
  if (!params) {
    return undefined;
  }
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null);
  if (entries.length === 0) {
    return undefined;
  }
  return Object.fromEntries(entries);
};

const get = async <T>(url: string, params?: AnyRecord) => {
  const response = await apiClient.get<ApiEnvelope<T>>(url, { params: normalizeParams(params) });
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
      totp_code?: string;
    }) => post<AuthTokens>("/auth/login", payload),
    refresh: () => post<AuthTokens>("/auth/refresh", { refresh_token: getRefreshToken() }),
    logout: () => post<{ logged_out: boolean }>("/auth/logout"),
    me: () => get<UserProfile>("/auth/me"),
    updateProfile: (payload: {
      full_name?: string;
      display_name?: string | null;
      avatar_url?: string | null;
      timezone?: string;
      wake_time?: string | null;
      sleep_time?: string | null;
      sleep_goal?: number | null;
      focus_areas?: string[] | null;
    }) => patch<UserProfile>("/auth/profile", payload),
    adminUsers: () => get<AdminUser[]>("/auth/admin/users"),
    adminUpdateUser: (userId: string, payload: { role?: string; is_active?: boolean }) =>
      patch<AdminUser>(`/auth/admin/users/${userId}`, payload),
    adminDeactivateUser: (userId: string) => del<AdminUser>(`/auth/admin/users/${userId}`),
    adminStats: () => get<AdminStats>("/auth/admin/stats"),
    inviteFamily: (payload: { email: string; role: "family" | "guest" }) =>
      post<Record<string, unknown>>("/auth/family/invite", payload),
    setup2fa: () => get<TotpSetupPayload>("/auth/2fa/setup"),
    verify2fa: (code: string) => post<{ enabled: boolean }>("/auth/2fa/verify", { code }),
    sessions: () => get<SessionDevice[]>("/auth/sessions"),
    revokeSession: (sessionId: string) => del<{ revoked: boolean }>(`/auth/sessions/${sessionId}`),
    loginHistory: (limit = 25) => get<LoginHistoryItem[]>("/auth/login-history", { limit }),
    onboardingStatus: () => get<OnboardingStatus>("/auth/onboarding/status"),
    completeOnboarding: (payload: OnboardingCompletePayload) =>
      post<OnboardingCompleteResponse>("/auth/onboarding/complete", payload),
  },

  security: {
    listSecrets: () => get<SecretMetadata[]>("/security/secrets"),
    rotateSecret: (payload: { provider: string; plaintext_key: string }) =>
      post<SecretMetadata>("/security/secrets/rotate", payload),
    revokeSecret: (secretId: string) => del<{ revoked: boolean }>(`/security/secrets/${secretId}`),
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

  briefing: {
    today: () => get<MorningBriefing>("/briefing/today"),
    sendNow: () => post<MorningBriefingSendResult>("/briefing/send-now"),
    weeklyReview: () => get<WeeklyReview>("/briefing/weekly-review"),
  },

  calendar: {
    today: async () => {
      const response = await apiClient.get<CalendarTodayResponse>("/calendar/today");
      return response.data;
    },
    upcoming: async (days = 7) => {
      const response = await apiClient.get<{ events: Array<Record<string, unknown>>; count: number }>(
        "/calendar/upcoming",
        { params: { days } },
      );
      return response.data;
    },
    syncGoogleToWilliam: async () => {
      const response = await apiClient.post<{ synced: number; added: number; updated: number; removed: number }>("/calendar/sync/google-to-william", {});
      return response.data;
    },
    syncWilliamToGoogle: async () => {
      const response = await apiClient.post<{ pushed: number }>("/calendar/sync/william-to-google", {});
      return response.data;
    },
    syncConflicts: async () => {
      const response = await apiClient.get<{ conflicts: CalendarSyncConflict[]; count: number }>("/calendar/sync/conflicts");
      return response.data;
    },
    listNativeEvents: async (days = 30) => {
      const response = await apiClient.get<{ events: CalendarEvent[]; count: number }>(
        "/calendar/native/events",
        { params: { days } },
      );
      return response.data;
    },
    createNativeEvent: async (payload: NativeCalendarEventPayload) => {
      const response = await apiClient.post<{ event: CalendarEvent; status: string }>(
        "/calendar/native/events",
        payload,
      );
      return response.data;
    },
    updateNativeEvent: async (eventId: string, payload: NativeCalendarEventPatch) => {
      const response = await apiClient.patch<{ event: CalendarEvent; status: string }>(
        `/calendar/native/events/${eventId}`,
        payload,
      );
      return response.data;
    },
    deleteNativeEvent: async (eventId: string) => {
      const response = await apiClient.delete<{ status: string; event_id: string }>(
        `/calendar/native/events/${eventId}`,
      );
      return response.data;
    },
  },

  feed: {
    list: (params?: { limit?: number; before_cursor?: string }) =>
      get<CursorPage<ActivityFeedItem>>("/feed", params),
  },

  agents: {
    status: () => get<AgentStatus[]>("/agents/status"),
    recommendations: (params?: { limit?: number }) =>
      get<AgentRecommendationLog[]>("/agents/recommendations", params),
    trigger: (name: string) => post<Record<string, unknown>>(`/agents/${name}/trigger`),
    runAll: () => post<AgentRunAllResult>("/agents/run-all"),
  },

  rules: {
    listRules: () => get<UserRule[]>("/rules"),
    getTemplates: () => get<RuleTemplate[]>("/rules/templates"),
    createRule: (payload: AnyRecord) => post<UserRule>("/rules", payload),
    updateRule: (ruleId: string, payload: AnyRecord) =>
      apiClient.put<ApiEnvelope<UserRule>>(`/rules/${ruleId}`, payload).then((response) => unwrap(response.data)),
    deleteRule: (ruleId: string) => del<{ deleted: boolean }>(`/rules/${ruleId}`),
    evaluateNow: () => post<RuleEvaluationResult>("/rules/evaluate-now"),

    // Backward-compatible aliases used by existing pages.
    list: () => get<UserRule[]>("/rules"),
    templates: () => get<RuleTemplate[]>("/rules/templates"),
    create: (payload: AnyRecord) => post<UserRule>("/rules", payload),
    update: (ruleId: string, payload: AnyRecord) =>
      apiClient.put<ApiEnvelope<UserRule>>(`/rules/${ruleId}`, payload).then((response) => unwrap(response.data)),
    put: (ruleId: string, payload: AnyRecord) =>
      apiClient.put<ApiEnvelope<UserRule>>(`/rules/${ruleId}`, payload).then((response) => unwrap(response.data)),
    remove: (ruleId: string) => del<{ deleted: boolean }>(`/rules/${ruleId}`),
  },

  gamification: {
    profile: () => get<GamificationProfile>("/gamification/profile"),
    xpHistory: (params?: { limit?: number; offset?: number }) =>
      get<GamificationXPEvent[]>("/gamification/xp-history", params),
    records: (params?: { limit?: number; offset?: number }) =>
      get<GamificationRecord[]>("/gamification/records", params),
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
    create: (payload: { content: string; passphrase?: string; mood?: string; tags?: string[] }) =>
      post<JournalEntryMeta>("/journal", payload),
    list: (params?: AnyRecord) => get<JournalEntryMeta[]>("/journal", params),
    unlock: (passphrase: string) => post<JournalUnlockResponse>("/journal/unlock", { passphrase }),
    getDraft: (passphrase?: string) => get<JournalDraft | null>("/journal/draft", { passphrase }),
    saveDraft: (payload: { content: string; passphrase?: string; mood?: string; tags?: string[] }) =>
      apiClient.put<ApiEnvelope<JournalDraft>>("/journal/draft", payload).then((response) => unwrap(response.data)),
    clearDraft: () => del<{ deleted: boolean }>("/journal/draft"),
    read: (entryId: string, passphrase?: string) => post<JournalEntryDecrypted>(`/journal/${entryId}/read`, { passphrase }),
    summary: (entryId: string, passphrase?: string) => post<JournalEntryDecrypted>(`/journal/${entryId}/summary`, { passphrase }),
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
    transcribe: async (audioBlob: Blob) => {
      const formData = new FormData();
      formData.append("audio", audioBlob, "voice-recording.webm");
      const response = await apiClient.post<ApiEnvelope<AnyRecord>>("/voice/transcribe", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return response.data.data;
    },
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
    dashboard: () => get<StudyDashboard>("/study/dashboard"),
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
    adjustments: () => get<Record<string, unknown>>("/intelligence/adjustments"),
    lifeScore: () => get<LifeScore>("/intelligence/life-score"),
    lifeScoreHistory: (days = 30) => get<LifeScoreHistoryPoint[]>("/intelligence/life-score/history", { days }),
    timeline: (days = 90) => get<TimelineEvent[]>("/intelligence/timeline", { days }),
    askTimeline: (question: string) => post<AskTimelineResponse>("/intelligence/ask-timeline", { question }),
    warnings: () => get<PredictiveWarning[]>("/intelligence/warnings"),
    scanWarnings: () => post<PredictiveWarning[]>("/intelligence/warnings/scan"),
    resolveWarning: (warningId: string) => patch<PredictiveWarning>(`/intelligence/warnings/${warningId}/resolve`),
    burnoutScore: () => get<BurnoutScorePayload>("/intelligence/burnout/score"),
    interveneBurnout: () => post<BurnoutInterventionPayload>("/intelligence/burnout/intervene"),
  },

  memory: {
    insights: () => get<Array<Record<string, unknown>>>("/memory/insights"),
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
    auditCsv: async () => {
      const response = await apiClient.get("/export/audit-log.csv", { responseType: "blob" });
      return response.data as Blob;
    },
    weeklyReportPdf: async () => {
      const response = await apiClient.get("/export/report/weekly.pdf.pdf", { responseType: "blob" });
      return response.data as Blob;
    },
    monthlyReportPdf: async () => {
      const response = await apiClient.get("/export/report/monthly.pdf.pdf", { responseType: "blob" });
      return response.data as Blob;
    },
    customReportPdf: async (days = 30) => {
      const response = await apiClient.get("/export/report/pdf", {
        params: { days },
        responseType: "blob",
      });
      return response.data as Blob;
    },
    deleteAccount: (password: string) => del<{ deleted: boolean }>("/export/account", { password }),
  },
  career: {
    dashboard: () => get<Record<string, unknown>>("/career/dashboard"),
    scoreHistory: (days = 30) => get<Array<Record<string, unknown>>>("/career/score/history", { days }),
    recomputeScore: () => post<Record<string, unknown>>("/career/score/recompute"),
    updateCFRating: (rating: number) => post<Record<string, unknown>>("/career/score/cf-rating", { rating }),

    listProblems: (params?: AnyRecord) => get<AnyRecord[]>("/career/problems", params),
    createProblem: (payload: AnyRecord) => post<AnyRecord>("/career/problems", payload),
    getProblem: (id: string) => get<AnyRecord>(`/career/problems/${id}`),
    updateProblem: (id: string, payload: AnyRecord) => patch<AnyRecord>(`/career/problems/${id}`, payload),
    deleteProblem: (id: string) => del<{ deleted: boolean }>(`/career/problems/${id}`),

    listProjects: () => get<AnyRecord[]>("/career/projects"),
    createProject: (payload: AnyRecord) => post<AnyRecord>("/career/projects", payload),
    getProject: (id: string) => get<AnyRecord>(`/career/projects/${id}`),
    updateProject: (id: string, payload: AnyRecord) => patch<AnyRecord>(`/career/projects/${id}`, payload),
    deleteProject: (id: string) => del<{ deleted: boolean }>(`/career/projects/${id}`),

    listApplications: (params?: AnyRecord) => get<AnyRecord[]>("/career/applications", params),
    createApplication: (payload: AnyRecord) => post<AnyRecord>("/career/applications", payload),
    getApplicationPipeline: () => get<Record<string, AnyRecord[]>>("/career/applications/pipeline"),
    getApplication: (id: string) => get<AnyRecord>(`/career/applications/${id}`),
    updateApplication: (id: string, payload: AnyRecord) => patch<AnyRecord>(`/career/applications/${id}`, payload),
    deleteApplication: (id: string) => del<{ deleted: boolean }>(`/career/applications/${id}`),
    updateApplicationStage: (id: string, stage: string) =>
      post<AnyRecord>(`/career/applications/${id}/stage`, { stage }),

    listContacts: (params?: AnyRecord) => get<AnyRecord[]>("/career/contacts", params),
    createContact: (payload: AnyRecord) => post<AnyRecord>("/career/contacts", payload),
    getContactFollowups: () => get<AnyRecord[]>("/career/contacts/followups"),
    getContact: (id: string) => get<AnyRecord>(`/career/contacts/${id}`),
    updateContact: (id: string, payload: AnyRecord) => patch<AnyRecord>(`/career/contacts/${id}`, payload),
    deleteContact: (id: string) => del<{ deleted: boolean }>(`/career/contacts/${id}`),
    draftContactMessage: (id: string, context?: string) =>
      post<{ draft: string; contact_id: string }>(`/career/contacts/${id}/draft-message`, { context }),

    listOpportunities: (params?: AnyRecord) => get<AnyRecord[]>("/career/opportunities", params),
    createOpportunity: (payload: AnyRecord) => post<AnyRecord>("/career/opportunities", payload),
    getOpportunity: (id: string) => get<AnyRecord>(`/career/opportunities/${id}`),
    updateOpportunity: (id: string, payload: AnyRecord) => patch<AnyRecord>(`/career/opportunities/${id}`, payload),
    deleteOpportunity: (id: string) => del<{ deleted: boolean }>(`/career/opportunities/${id}`),
    convertOpportunity: (id: string, payload: { role: string; platform?: string }) =>
      post<AnyRecord>(`/career/opportunities/${id}/convert`, payload),
  },

  chat: {
    createSession: (payload: { agent_name: string; title: string }) => 
      post<ChatSession>("/chat/sessions", payload),
    listSessions: () => get<ChatSessionListItem[]>("/chat/sessions"),
    deleteSession: (sessionId: string) => del<{ deleted: boolean }>(`/chat/sessions/${sessionId}`),
    sendMessage: (sessionId: string, payload: { content: string }) => 
      post<{ user_message: ChatMessage; assistant_message: ChatMessage }>(`/chat/sessions/${sessionId}/messages`, payload),
    streamMessage: async (
      sessionId: string,
      payload: { content: string },
      onEvent: (event: ChatStreamEvent) => void,
    ) => {
      const token = getAccessToken();
      const response = await fetch(`${baseURL}/chat/sessions/${sessionId}/messages/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) {
        throw new Error("Failed to stream chat response");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          if (block) {
            const lines = block.split("\n");
            const eventLine = lines.find((line) => line.startsWith("event:"));
            const dataLine = lines.find((line) => line.startsWith("data:"));
            if (eventLine && dataLine) {
              const eventName = eventLine.replace("event:", "").trim();
              const payloadText = dataLine.replace("data:", "").trim();
              try {
                const parsed = JSON.parse(payloadText);
                if (
                  eventName === "status"
                  || eventName === "user_message"
                  || eventName === "delta"
                  || eventName === "done"
                ) {
                  onEvent({ event: eventName, data: parsed } as ChatStreamEvent);
                }
              } catch {
                // Ignore malformed partial event payloads.
              }
            }
          }
          boundary = buffer.indexOf("\n\n");
        }
      }
    },
    getMessages: (sessionId: string, params?: { limit?: number }) => 
      get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, params),
    triggerProactive: (trigger: "morning" | "afternoon" | "evening") =>
      post<{ message: string; sent: boolean }>("/chat/proactive/trigger", { trigger }),
  },
};
