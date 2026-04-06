export type ApiEnvelope<T> = {
  ok: boolean;
  data: T;
  error?: string;
  meta?: Record<string, unknown>;
};

export type AnyRecord = Record<string, unknown>;

export type UserProfile = {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  timezone?: string;
  role?: string;
  wake_time?: string;
  sleep_time?: string;
  [key: string]: unknown;
};

export type AuthTokens = {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
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
  [key: string]: unknown;
};
