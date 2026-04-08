export type ApiEnvelope<T> = {
  ok: boolean;
  data: T;
  error?: string;
  meta?: Record<string, unknown>;
};

export type CursorPage<T> = {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
  total?: number | null;
};

export type AnyRecord = Record<string, unknown>;

export type UserProfile = {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  display_name?: string | null;
  timezone?: string;
  role?: string;
  wake_time?: string | null;
  sleep_time?: string;
  sleep_goal?: number | null;
  focus_areas?: string[];
  onboarding_completed?: boolean;
  [key: string]: unknown;
};

export type OnboardingStatus = {
  completed: boolean;
};

export type OnboardingCompletePayload = {
  display_name: string;
  wake_time: string;
  sleep_goal: number;
  focus_areas: string[];
  goals: string;
};

export type OnboardingCompleteResponse = {
  status: string;
  habits_created: string[];
  message: string;
};

export type AuthTokens = {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
};

export type TotpSetupPayload = {
  otp_auth_url: string;
  qr_code_data_url: string;
  secret_preview: string;
};

export type SessionDevice = {
  id: string;
  device_name: string;
  device_type: string;
  device_fingerprint: string;
  last_active: string | null;
  is_active: boolean;
  created_at: string;
  is_current: boolean;
};

export type LoginHistoryItem = {
  id: string;
  ip: string | null;
  country: string | null;
  device_fingerprint: string;
  user_agent: string | null;
  success: boolean;
  timestamp: string;
};

export type SecretMetadata = {
  id: string;
  provider: string;
  key_hint: string;
  version: number;
  is_active: boolean;
  rotated_at: string;
};

export type ScheduleBlock = {
  id: string;
  title: string;
  description?: string;
  category: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: string;
  priority: number;
  tags?: string[];
  is_fixed?: boolean;
  is_ai_generated?: boolean;
  [key: string]: unknown;
};

export type DailyPlan = {
  id: string;
  plan_date: string;
  status: string;
  generation_model?: string;
  completion_score?: number | null;
  energy_score?: number | null;
  blocks: ScheduleBlock[];
  [key: string]: unknown;
};

export type Habit = {
  id: string;
  name: string;
  icon: string;
  category?: string;
  current_streak?: number;
  best_streak?: number;
  total_completions?: number;
  is_active?: boolean;
  preferred_time?: string | null;
  auto_schedule?: boolean;
  schedule_category?: string;
  [key: string]: unknown;
};

export type HabitCheckIn = {
  id: string;
  habit_id: string;
  check_date: string;
  completed: boolean;
  skipped: boolean;
  completed_at?: string | null;
  [key: string]: unknown;
};

export type JournalEntryMeta = {
  id: string;
  entry_date: string;
  mood?: string | null;
  tags?: string[];
  word_count?: number;
  summary?: string | null;
  [key: string]: unknown;
};

export type JournalEntryDecrypted = JournalEntryMeta & {
  content: string;
};

export type Medicine = {
  id: string;
  name: string;
  dosage: string;
  medicine_type?: string;
  reminder_times?: string[];
  remaining_count?: number | null;
  refill_reminder_days?: number;
  is_active?: boolean;
  [key: string]: unknown;
};

export type MedicineReminder = {
  medicine_name: string;
  dosage: string;
  scheduled_time: string;
  with_food?: boolean;
  instructions?: string | null;
};

export type Subject = {
  id: string;
  name: string;
  color?: string;
  [key: string]: unknown;
};

export type StudySession = {
  id: string;
  subject_id: string;
  duration_minutes: number;
  session_date: string;
  comprehension_score?: number;
  topics_covered?: string[];
  [key: string]: unknown;
};

export type RevisionCard = {
  id: string;
  subject_id: string;
  question: string;
  answer: string;
  next_review_date: string;
  repetitions: number;
  interval_days: number;
  [key: string]: unknown;
};

export type MockTest = {
  id: string;
  test_name: string;
  score: number;
  total: number;
  percentage: number;
  date: string;
  [key: string]: unknown;
};

export type Workout = {
  id: string;
  activity: string;
  duration_minutes: number;
  calories_burned?: number;
  workout_date: string;
  [key: string]: unknown;
};

export type EnergyForecast = {
  id: string;
  forecast_date: string;
  peak_hours: string[];
  low_hours: string[];
  hourly_scores?: Record<string, number>;
  suggestions?: string[];
  [key: string]: unknown;
};

export type LifeScore = {
  id: string;
  user_id: string;
  score: number;
  component_scores: Record<string, number>;
  explanation: string;
  computed_at: string;
  created_at: string;
};

export type LifeScoreHistoryPoint = {
  score: number;
  computed_at: string;
};

export type BriefingScheduleItem = {
  id: string;
  title: string;
  category: string;
  start_time: string;
  end_time: string;
  priority: number;
  status: string;
};

export type BriefingHabitItem = {
  id: string;
  name: string;
  preferred_time?: string | null;
  current_streak: number;
};

export type BriefingMedicineMissItem = {
  medicine_name: string;
  log_date: string;
  scheduled_time: string;
  skip_reason?: string | null;
};

export type BriefingDeadlineItem = {
  source: string;
  title: string;
  due_date: string;
  detail?: string | null;
};

export type BriefingEnergyPrediction = {
  peak_hours: string[];
  low_hours: string[];
  suggestions: string[];
  generated_by?: string | null;
};

export type BriefingLifeScore = {
  score: number;
  component_scores: Record<string, number>;
  explanation: string;
  computed_at: string;
};

export type MorningBriefing = {
  generated_at: string;
  sleep_quality: Record<string, unknown>;
  today_schedule: BriefingScheduleItem[];
  priority_habits: BriefingHabitItem[];
  missed_medicines: BriefingMedicineMissItem[];
  upcoming_deadlines: BriefingDeadlineItem[];
  market_watchlist_movement: {
    watchlist_count?: number;
    top_gainers?: Array<Record<string, unknown>>;
    top_losers?: Array<Record<string, unknown>>;
  };
  energy_prediction: BriefingEnergyPrediction | null;
  life_score: BriefingLifeScore;
  ai_recommendation_of_day: string;
};

export type MorningBriefingSendResult = {
  briefing: MorningBriefing;
  telegram: NotificationItem;
  in_app: NotificationItem;
};

export type GamificationXPEvent = {
  id: string;
  user_id: string;
  source_module: string;
  action: string;
  xp_earned: number;
  earned_at: string;
};

export type GamificationRecord = {
  id: string;
  user_id: string;
  record_type: string;
  value: number;
  achieved_at: string;
};

export type GamificationWeeklyMomentum = {
  id: string;
  user_id: string;
  week_start: string;
  momentum_score: number;
  discipline_debt: number;
  focus_rank: number;
};

export type GamificationLevelProgress = {
  level: number;
  total_xp: number;
  current_level_xp_floor: number;
  next_level_xp_target: number;
  xp_to_next_level: number;
  progress_pct: number;
};

export type GamificationProfile = {
  level_progress: GamificationLevelProgress;
  weekly_momentum: GamificationWeeklyMomentum;
  records: GamificationRecord[];
  recent_xp_events: GamificationXPEvent[];
};

export type ActivityFeedItem = {
  event_id: string;
  timestamp: string;
  module: string;
  action: string;
  summary: string;
  icon_key: string;
  xp_earned?: number | null;
};

export type PredictiveWarning = {
  id: string;
  user_id: string;
  warning_type: string;
  severity: "low" | "medium" | "high" | "critical" | string;
  explanation: string;
  recommended_action: string;
  details: Record<string, unknown>;
  is_active: boolean;
  detected_at: string;
  resolved_at?: string | null;
};

export type AgentStatus = {
  id: string;
  user_id: string;
  agent_name: string;
  description: string;
  status: string;
  last_recommendation: Record<string, unknown>;
  last_action: Record<string, unknown>;
  last_run_at: string;
};

export type AgentRecommendationLog = {
  id: string;
  user_id: string;
  agent_name: string;
  severity: string;
  urgency: number;
  recommendation: Record<string, unknown>;
  status: string;
  is_active: boolean;
  created_at: string;
};

export type UserRule = {
  id: string;
  user_id: string;
  name: string;
  trigger_module: string;
  trigger_condition: Record<string, unknown>;
  action_module: string;
  action_type: string;
  action_params: Record<string, unknown>;
  is_active: boolean;
  last_triggered?: string | null;
  created_at: string;
};

export type RuleTemplate = {
  name: string;
  trigger_module: string;
  trigger_condition: Record<string, unknown>;
  action_module: string;
  action_type: string;
  action_params: Record<string, unknown>;
};

export type RuleEvaluationLog = {
  id: string;
  user_id: string;
  rule_id: string;
  matched: boolean;
  action_success: boolean;
  context_snapshot: Record<string, unknown>;
  action_result: Record<string, unknown>;
  error?: string | null;
  executed_at: string;
  created_at: string;
};

export type RuleEvaluationResult = {
  evaluated: number;
  matched: number;
  executed: number;
  logs: RuleEvaluationLog[];
};

export type Trade = {
  id: string;
  symbol: string;
  exchange: string;
  action: string;
  quantity: number;
  price: number;
  total_value: number;
  trade_date: string;
  [key: string]: unknown;
};

export type PortfolioSummary = {
  total_invested: number;
  current_value: number;
  total_pnl: number;
  total_pnl_pct?: number;
  daily_pnl?: number;
  holdings_count?: number;
  top_gainers?: Array<Record<string, unknown>>;
  top_losers?: Array<Record<string, unknown>>;
  [key: string]: unknown;
};

export type SleepRecord = {
  id: string;
  sleep_date: string;
  sleep_duration_minutes: number;
  sleep_quality: number;
  bedtime: string;
  wake_time: string;
  [key: string]: unknown;
};

export type SleepStats = {
  avg_quality_30d: number;
  avg_duration: number;
  avg_bedtime: string;
  consistency_score: number;
};

export type SleepRecommendation = {
  id: string;
  recommendation_date: string;
  recommended_bedtime: string;
  recommended_wake_time: string;
  recommended_duration_minutes: number;
  reasoning: string;
  [key: string]: unknown;
};

export type Decision = {
  id: string;
  title: string;
  decision_type: string;
  status: string;
  options: Array<Record<string, unknown>>;
  criteria: Array<Record<string, unknown>>;
  deadline?: string | null;
  chosen_option?: string | null;
  outcome_rating?: number | null;
  [key: string]: unknown;
};

export type DecisionAnalysis = {
  scores: Record<string, number>;
  recommendation: string;
  reasoning: string;
  confidence: number;
  risk_factors: string[];
};

export type NotificationItem = {
  id: string;
  channel?: string;
  notification_type: string;
  sent_at: string;
  delivered: boolean;
  payload?: Record<string, unknown>;
  error?: string | null;
  [key: string]: unknown;
};

export type VoiceHistoryItem = {
  id: string;
  transcription: string;
  intent: string;
  intent_confidence: number;
  response_text: string;
  created_at: string;
}

export type ChatSession = {
  id: string;
  user_id: string;
  agent_name: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message?: ChatMessage | null;
};

export type ChatSessionListItem = {
  id: string;
  user_id: string;
  agent_name: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_preview?: string | null;
};

export type ChatMessage = {
  id: string;
  session_id: string;
  user_id: string;
  role: "user" | "assistant";
  content: string;
  actions_taken?: Array<{
    type: string;
    params: Record<string, unknown>;
    success: boolean;
    message: string;
    data?: Record<string, unknown> | null;
  }> | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};


export type AgentName = "health" | "study" | "trading" | "executive" | "recovery" | "os";
