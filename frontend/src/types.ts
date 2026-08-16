export type ParsedExpense = {
  amount: number | string;
  currency: string;
  category: string;
  subcategory: string | null;
  merchant: string | null;
  description: string | null;
  date: string;
  payment_method: string | null;
  notes: string | null;
  category_uncertain: boolean;
};

export type Expense = {
  id: number;
  amount: number | string;
  amount_cents: number;
  currency: string;
  date: string;
  merchant: string | null;
  description: string | null;
  category: string;
  category_id: number;
  subcategory: string | null;
  payment_method: string | null;
  notes: string | null;
  source: string;
  category_uncertain: boolean;
  is_recurring: boolean;
};

export type Dashboard = {
  month: string;
  empty: boolean;
  summary: {
    year: number;
    month: number;
    label: string;
    total_cents: number;
    total: string;
    count: number;
    average_cents: number;
    average: string;
    average_daily_cents: number;
    average_daily: string;
    largest: {
      amount_cents: number;
      merchant: string | null;
      description: string | null;
      category: string;
    } | null;
    top_category: { name: string; cents: number } | null;
    top_merchant: { name: string; cents: number } | null;
    vs_last_month_cents: number;
    vs_last_month_percent: string | null;
    previous_month_label: string;
  };
  categories: { category: string; cents: number; amount: string; percent: number }[];
  daily: { date: string; cents: number; amount: string; cumulative_cents: number; cumulative: string }[];
  trend: { key: string; label: string; cents: number; amount: string }[];
  category_compare: {
    category: string;
    current_cents: number;
    previous_cents: number;
    delta_cents: number;
    percent: string | null;
  }[];
  recent: {
    id: number;
    date: string;
    merchant: string | null;
    description: string | null;
    category: string;
    amount_cents: number;
    amount: string;
  }[];
};

export type HistoryMonth = {
  key: string;
  label: string;
  short_label: string;
  year: number;
  month: number;
  total_cents: number;
  count: number;
  average_cents: number;
  top_category: { name: string; cents: number } | null;
  top_merchant: { name: string; cents: number } | null;
  largest: {
    amount_cents: number;
    merchant: string | null;
    description: string | null;
    category: string;
  } | null;
  vs_last_month_cents: number;
  vs_last_month_percent: string | null;
  categories: { category: string; cents: number; amount: string; percent: number }[];
};

export type History = {
  chart: HistoryMonth[];
  months: HistoryMonth[];
  range_total_cents: number;
  range_count: number;
  peak: HistoryMonth | null;
  months_count: number;
  start_label: string;
  end_label: string;
};

export type Category = {
  id: number;
  name: string;
  icon: string;
  is_custom: boolean;
};

export type Settings = {
  default_currency: string;
  timezone: string;
  week_start: string;
  theme: string;
  ai_provider: string;
  auto_save_ai: boolean;
  openai_model: string;
  anthropic_model: string;
  ollama_model: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
};

export type Budget = {
  id: number;
  category: string;
  month: string;
  amount_cents: number;
  spent_cents: number;
  remaining_cents: number;
  percent: number;
};
