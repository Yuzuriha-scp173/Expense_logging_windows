import type { Budget, Category, Dashboard, Expense, History, ParsedExpense, Settings } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = await response.json();
    } catch {
      /* ignore */
    }
    const error = new Error("Request failed") as Error & { status: number; detail: unknown };
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  if (response.headers.get("content-type")?.includes("text/csv")) {
    return (await response.text()) as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  parse: (text: string, timezone: string) =>
    request<{ expenses: ParsedExpense[]; parser: string; warnings: string[]; duplicates: unknown[] }>(
      "/api/expenses/parse",
      { method: "POST", body: JSON.stringify({ text, timezone }) },
    ),
  createExpense: (payload: Record<string, unknown>, force = false) =>
    request<Expense>(`/api/expenses${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createMany: (payload: Record<string, unknown>[], force = false) =>
    request<Expense[]>(`/api/expenses/bulk${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listExpenses: (params: Record<string, string | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) q.set(k, v);
    });
    return request<Expense[]>(`/api/expenses?${q.toString()}`);
  },
  updateExpense: (id: number, payload: Record<string, unknown>) =>
    request<Expense>(`/api/expenses/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteExpense: (id: number) => request<{ ok: boolean }>(`/api/expenses/${id}`, { method: "DELETE" }),
  dashboard: (month: string, timezone: string) =>
    request<Dashboard>(`/api/summary/dashboard?month=${month}&timezone=${encodeURIComponent(timezone)}`),
  history: (month: string, timezone: string) =>
    request<History>(`/api/summary/history?month=${month}&timezone=${encodeURIComponent(timezone)}`),
  insights: (month: string) => request<{ insights: { id: string; text: string }[]; narrative: { text: string } }>(`/api/summary/insights?month=${month}`),
  categories: () => request<Category[]>("/api/categories"),
  subcategories: () => request<Record<string, string[]>>("/api/categories/subcategories"),
  addCategory: (name: string) =>
    request<Category>("/api/categories", { method: "POST", body: JSON.stringify({ name, icon: "circle" }) }),
  settings: () => request<Settings>("/api/settings"),
  saveSettings: (payload: Partial<Settings>) =>
    request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  ask: (question: string, timezone: string) =>
    request<{ explanation: string; result: Record<string, unknown>; intent: string }>(
      "/api/assistant/query",
      { method: "POST", body: JSON.stringify({ question, timezone }) },
    ),
  exportCsv: () => request<string>("/api/export.csv"),
  backup: () => request<{ path: string }>("/api/backup", { method: "POST" }),
  rules: () =>
    request<{ id: number; merchant_pattern: string; preferred_category: string; preferred_subcategory: string | null }[]>(
      "/api/rules",
    ),
  deleteRule: (id: number) => request(`/api/rules/${id}`, { method: "DELETE" }),
  subscriptions: () =>
    request<
      {
        merchant: string;
        typical: string;
        interval: string;
        monthly: string;
        annual: string;
        category: string;
        count: number;
      }[]
    >("/api/subscriptions"),
  budgets: (month: string) => request<Budget[]>(`/api/budgets?month=${month}`),
  saveBudget: (payload: { category: string; month: string; amount: number }) =>
    request<Budget>("/api/budgets", { method: "POST", body: JSON.stringify(payload) }),
};

export function money(cents: number): string {
  const abs = Math.abs(cents) / 100;
  const formatted = abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${cents < 0 ? "-" : ""}$${formatted}`;
}

export function currentMonth(timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit" }).formatToParts(
    new Date(),
  );
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  return `${year}-${month}`;
}

export function shiftMonth(key: string, delta: number): string {
  const [y, m] = key.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function prettyDate(iso: string): string {
  const today = new Date();
  const value = new Date(`${iso}T12:00:00`);
  const same = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (same(value, today)) return "Today";
  if (same(value, yesterday)) return "Yesterday";
  return value.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function localTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
