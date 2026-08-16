import { FormEvent, useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, currentMonth, localTimezone, money, monthLabel, prettyDate, shiftMonth } from "./api";
import type { Category, Dashboard, Expense, History, ParsedExpense, Settings } from "./types";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Toast = { text: string } | null;

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [month, setMonth] = useState(() => currentMonth(localTimezone()));
  const [categories, setCategories] = useState<Category[]>([]);

  function notify(text: string) {
    setToast({ text });
    window.setTimeout(() => setToast(null), 2800);
  }

  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      applyTheme(s.theme);
      setMonth(currentMonth(s.timezone || localTimezone()));
    });
    api.categories().then(setCategories);
  }, []);

  if (!settings) {
    return (
      <div className="main">
        <div className="skeleton" style={{ width: 240, height: 28 }} />
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <strong>Daybook</strong>
          <span>A simple money journal</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/expenses">Expenses</NavLink>
          <NavLink to="/history">History</NavLink>
          <NavLink to="/insights">Insights</NavLink>
          <NavLink to="/budgets">Budgets</NavLink>
          <NavLink to="/subscriptions">Subscriptions</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                month={month}
                setMonth={setMonth}
                settings={settings}
                categories={categories}
                notify={notify}
              />
            }
          />
          <Route
            path="/expenses"
            element={
              <ExpensesPage month={month} setMonth={setMonth} categories={categories} notify={notify} settings={settings} />
            }
          />
          <Route
            path="/history"
            element={<HistoryPage month={month} setMonth={setMonth} settings={settings} />}
          />
          <Route path="/insights" element={<InsightsPage month={month} setMonth={setMonth} settings={settings} />} />
          <Route path="/budgets" element={<BudgetsPage month={month} categories={categories} notify={notify} />} />
          <Route path="/subscriptions" element={<SubscriptionsPage />} />
          <Route
            path="/settings"
            element={<SettingsPage settings={settings} setSettings={setSettings} categories={categories} setCategories={setCategories} notify={notify} />}
          />
        </Routes>
      </main>
      {toast ? <div className="toast" role="status">{toast.text}</div> : null}
    </div>
  );
}

function applyTheme(theme: string) {
  const dark =
    theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function MonthNav({ month, setMonth }: { month: string; setMonth: (m: string) => void }) {
  const options = useMemo(() => {
    const items: string[] = [];
    let cursor = currentMonth(localTimezone());
    for (let i = 0; i < 24; i += 1) {
      items.push(cursor);
      cursor = shiftMonth(cursor, -1);
    }
    return items;
  }, []);
  return (
    <div className="month-nav">
      <button type="button" aria-label="Previous month" onClick={() => setMonth(shiftMonth(month, -1))}>
        ←
      </button>
      <select aria-label="Select month" value={month} onChange={(e) => setMonth(e.target.value)}>
        {options.map((key) => (
          <option key={key} value={key}>
            {monthLabel(key)}
          </option>
        ))}
      </select>
      <button type="button" aria-label="Next month" onClick={() => setMonth(shiftMonth(month, 1))}>
        →
      </button>
    </div>
  );
}

function Composer({
  settings,
  categories,
  notify,
  onSaved,
}: {
  settings: Settings;
  categories: Category[];
  notify: (t: string) => void;
  onSaved: () => void;
}) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState<ParsedExpense[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [dup, setDup] = useState(false);

  async function parse(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.parse(text.trim(), settings.timezone);
      if (!result.expenses.length) {
        setError("Could not understand that. Try an amount, like “$12 lunch”, or enter it manually.");
        setPending(null);
        return;
      }
      if (result.warnings.length) setError(result.warnings[0]);
      setDup(result.duplicates.length > 0);
      if (settings.auto_save_ai) {
        await save(result.expenses, false);
        return;
      }
      setPending(result.expenses);
    } catch {
      setError("AI parsing is temporarily unavailable. You can still enter the expense manually.");
      setManual(true);
    } finally {
      setBusy(false);
    }
  }

  async function save(items: ParsedExpense[], force: boolean) {
    try {
      const payloads = items.map((item) => ({ ...item, source: "AI_TEXT" }));
      if (payloads.length === 1) {
        await api.createExpense(payloads[0], force);
      } else {
        await api.createMany(payloads, force);
      }
      const first = items[0];
      const who = first.merchant || first.description || first.category;
      notify(items.length === 1 ? `Expense added — $${Number(first.amount).toFixed(2)} at ${who}.` : `${items.length} expenses added.`);
      setPending(null);
      setText("");
      setDup(false);
      onSaved();
    } catch (err) {
      const e = err as { status?: number };
      if (e.status === 409) setDup(true);
      else setError("Could not save. Nothing was lost — try again.");
    }
  }

  return (
    <section>
      <form className="composer" onSubmit={parse}>
        <input
          aria-label="What did you spend?"
          placeholder="What did you spend?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          autoFocus
        />
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? "Reading…" : "Add"}
        </button>
        <button className="ghost" type="button" onClick={() => setManual(true)}>
          Manual
        </button>
      </form>
      <p className="hint">Try “Spent $18.50 on lunch at Chipotle” — or several amounts in one line.</p>
      {error ? <p className="error">{error}</p> : null}
      {pending ? (
        <div className="confirm">
          {dup ? <p className="warn">This expense may already exist.</p> : null}
          <div className="confirm-list">
            {pending.map((item, idx) => (
              <div className="confirm-row" key={`${item.amount}-${idx}`}>
                <strong>${Number(item.amount).toFixed(2)}</strong>
                <div>
                  <div>{item.merchant || "Unknown"}</div>
                  <div className="meta">{item.description || "—"}</div>
                </div>
                <div>
                  {item.category}
                  {item.category_uncertain ? " · uncertain" : ""}
                  <div className="meta">{prettyDate(item.date)}</div>
                </div>
                <div className="actions">
                  <button className="btn-primary" type="button" onClick={() => save(pending, dup)}>
                    {dup ? "Save anyway" : "Save"}
                  </button>
                  <button className="ghost" type="button" onClick={() => { setManual(true); }}>
                    Edit
                  </button>
                  <button className="ghost" type="button" onClick={() => setPending(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {manual ? (
        <ExpenseForm
          categories={categories}
          initial={pending?.[0]}
          onClose={() => setManual(false)}
          onSave={async (payload, force) => {
            await api.createExpense({ ...payload, source: pending ? "AI_TEXT" : "MANUAL" }, force);
            notify(`Expense added — $${Number(payload.amount).toFixed(2)}${payload.merchant ? ` at ${payload.merchant}` : ""}.`);
            setManual(false);
            setPending(null);
            setText("");
            onSaved();
          }}
        />
      ) : null}
    </section>
  );
}

function DashboardPage({
  month,
  setMonth,
  settings,
  categories,
  notify,
}: {
  month: string;
  setMonth: (m: string) => void;
  settings: Settings;
  categories: Category[];
  notify: (t: string) => void;
}) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [cumulative, setCumulative] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  function reload() {
    setLoading(true);
    api.dashboard(month, settings.timezone).then((d) => {
      setData(d);
      setLoading(false);
    });
  }

  useEffect(() => {
    reload();
  }, [month, settings.timezone]);

  useEffect(() => {
    if (location.hash === "#add") {
      document.querySelector<HTMLInputElement>('input[aria-label="What did you spend?"]')?.focus();
    }
  }, [location.hash]);

  const vs = data?.summary.vs_last_month_cents ?? 0;

  return (
    <>
      <div className="topbar">
        <h1>Expense journal</h1>
        <MonthNav month={month} setMonth={setMonth} />
      </div>
      <Composer settings={settings} categories={categories} notify={notify} onSaved={reload} />
      {loading || !data ? (
        <div className="skeleton" style={{ height: 72, marginTop: 24 }} />
      ) : data.empty ? (
        <div className="empty">
          <h2>No expenses yet this month.</h2>
          <p>Add your first expense.</p>
        </div>
      ) : (
        <>
          <div className="receipt">
            <p className="total">{money(data.summary.total_cents)}</p>
            <p className="caption">
              <span>Spent {data.summary.label}</span>
              <span className={vs > 0 ? "delta up" : "delta down"}>
                {vs === 0
                  ? `Same as ${data.summary.previous_month_label}`
                  : `${vs > 0 ? "+" : ""}${money(vs)} vs ${data.summary.previous_month_label}${
                      data.summary.vs_last_month_percent ? ` (${data.summary.vs_last_month_percent}%)` : ""
                    }`}
              </span>
            </p>
          </div>
          <div className="stats">
            <div className="stat">
              <div className="k">Per day</div>
              <div className="v">{money(data.summary.average_daily_cents)}</div>
            </div>
            <div className="stat">
              <div className="k">Transactions</div>
              <div className="v">{data.summary.count}</div>
            </div>
            <div className="stat">
              <div className="k">Largest</div>
              <div className="v">{data.summary.largest ? money(data.summary.largest.amount_cents) : "—"}</div>
            </div>
            <div className="stat">
              <div className="k">Top category</div>
              <div className="v">{data.summary.top_category?.name ?? "—"}</div>
            </div>
          </div>
          <div className="grid-2">
            <section className="panel">
              <h2>Spending by category</h2>
              <div className="bars">
                {data.categories.map((row) => (
                  <div className="bar-row" key={row.category}>
                    <span>{row.category}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${Math.max(row.percent, 2)}%` }} />
                    </div>
                    <span className="amt">
                      {money(row.cents)} · {row.percent}%
                    </span>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel">
              <h2>
                Daily spending{" "}
                <button className="ghost" type="button" onClick={() => setCumulative((v) => !v)}>
                  {cumulative ? "Daily" : "Cumulative"}
                </button>
              </h2>
              <div className="chart">
                <ResponsiveContainer>
                  <AreaChart data={data.daily}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={(v) => String(v).slice(8)} tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v) => `$${Number(v) / 100}`} tick={{ fontSize: 11 }} width={48} />
                    <Tooltip formatter={(v) => money(Number(v))} />
                    <Area
                      type="monotone"
                      dataKey={cumulative ? "cumulative_cents" : "cents"}
                      stroke="var(--sage)"
                      fill="var(--sage-soft)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>
          <section className="panel">
            <h2>Monthly trend</h2>
            <div className="chart">
              <ResponsiveContainer>
                <BarChart data={data.trend}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `$${Number(v) / 100}`} tick={{ fontSize: 11 }} width={48} />
                  <Tooltip formatter={(v) => money(Number(v))} />
                  <Bar dataKey="cents" fill="var(--sage)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="panel" style={{ marginTop: 32 }}>
            <h2>Recent expenses</h2>
            {data.recent.map((row) => (
              <div className="expense-row" key={row.id}>
                <div className="meta">{prettyDate(row.date)}</div>
                <div>
                  <div className="who">{row.merchant || row.description || "Expense"}</div>
                  <div className="meta">
                    {row.category}
                    {row.description && row.merchant ? ` · ${row.description}` : ""}
                  </div>
                </div>
                <div className="amt">{money(row.amount_cents)}</div>
                <div />
              </div>
            ))}
            <p>
              <button className="ghost" type="button" onClick={() => navigate("/expenses")}>
                All expenses
              </button>
            </p>
          </section>
        </>
      )}
      <button className="quick-add" type="button" onClick={() => navigate("/#add")}>
        + Expense
      </button>
    </>
  );
}

function HistoryPage({
  month,
  setMonth,
  settings,
}: {
  month: string;
  setMonth: (m: string) => void;
  settings: Settings;
}) {
  const [data, setData] = useState<History | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(month);
  const navigate = useNavigate();

  useEffect(() => {
    api.history(month, settings.timezone).then(setData);
  }, [month, settings.timezone]);

  if (!data) {
    return (
      <>
        <div className="topbar">
          <h1>History</h1>
        </div>
        <div className="skeleton" style={{ height: 72 }} />
      </>
    );
  }

  const empty = data.range_count === 0;

  return (
    <>
      <div className="topbar">
        <h1>History</h1>
      </div>
      <p className="hint">
        {data.start_label} – {data.end_label}. Open a month to see where the money went.
      </p>
      {empty ? (
        <div className="empty">
          <h2>No spending in the past 12 months.</h2>
          <p>Add expenses and they will appear here by month.</p>
        </div>
      ) : (
        <>
          <div className="receipt">
            <p className="total">{money(data.range_total_cents)}</p>
            <p className="caption">
              <span>Spent over 12 months</span>
              <span>
                {data.range_count} expense{data.range_count === 1 ? "" : "s"}
                {data.peak ? ` · Highest ${data.peak.label}` : ""}
              </span>
            </p>
          </div>
          <section className="panel">
            <h2>Monthly spending</h2>
            <div className="chart tall">
              <ResponsiveContainer>
                <BarChart data={data.chart}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="short_label" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `$${Number(v) / 100}`} tick={{ fontSize: 11 }} width={48} />
                  <Tooltip
                    formatter={(v) => money(Number(v))}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ""}
                  />
                  <Bar dataKey="total_cents" fill="var(--sage)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="panel" style={{ marginTop: 32 }}>
            <h2>By month</h2>
            {data.months.map((row) => {
              const open = openKey === row.key;
              const delta = row.vs_last_month_cents;
              return (
                <div key={row.key}>
                  <button
                    type="button"
                    className={`history-row${open ? " open" : ""}`}
                    aria-expanded={open}
                    onClick={() => setOpenKey(open ? null : row.key)}
                  >
                    <div>
                      <div className="who">{row.label}</div>
                      <div className="meta">
                        {row.count === 0
                          ? "No expenses"
                          : `${row.count} expense${row.count === 1 ? "" : "s"}`}
                        {row.top_category ? ` · ${row.top_category.name}` : ""}
                      </div>
                    </div>
                    <div className="meta">
                      {row.count === 0
                        ? ""
                        : delta === 0
                          ? "Same as prior month"
                          : `${delta > 0 ? "+" : ""}${money(delta)}${
                              row.vs_last_month_percent ? ` (${row.vs_last_month_percent}%)` : ""
                            }`}
                    </div>
                    <div className="amt">{money(row.total_cents)}</div>
                  </button>
                  {open ? (
                    <div className="history-detail">
                      {row.count === 0 ? (
                        <p className="hint">No expenses this month.</p>
                      ) : (
                        <>
                          <div className="stats">
                            <div className="stat">
                              <div className="k">Average</div>
                              <div className="v">{money(row.average_cents)}</div>
                            </div>
                            <div className="stat">
                              <div className="k">Largest</div>
                              <div className="v">{row.largest ? money(row.largest.amount_cents) : "—"}</div>
                            </div>
                            <div className="stat">
                              <div className="k">Top merchant</div>
                              <div className="v">{row.top_merchant?.name ?? "—"}</div>
                            </div>
                            <div className="stat">
                              <div className="k">Top category</div>
                              <div className="v">{row.top_category?.name ?? "—"}</div>
                            </div>
                          </div>
                          <div className="bars">
                            {row.categories.map((cat) => (
                              <div className="bar-row" key={cat.category}>
                                <span>{cat.category}</span>
                                <div className="bar-track">
                                  <div className="bar-fill" style={{ width: `${Math.max(cat.percent, 2)}%` }} />
                                </div>
                                <span className="amt">
                                  {money(cat.cents)} · {cat.percent}%
                                </span>
                              </div>
                            ))}
                          </div>
                          <p style={{ marginTop: 12 }}>
                            <button
                              className="ghost"
                              type="button"
                              onClick={() => {
                                setMonth(row.key);
                                navigate("/");
                              }}
                            >
                              Open {row.label} on Dashboard
                            </button>
                          </p>
                        </>
                      )}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </section>
        </>
      )}
    </>
  );
}

function ExpensesPage({
  month,
  setMonth,
  categories,
  notify,
  settings,
}: {
  month: string;
  setMonth: (m: string) => void;
  categories: Category[];
  notify: (t: string) => void;
  settings: Settings;
}) {
  const [rows, setRows] = useState<Expense[] | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("newest");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [editing, setEditing] = useState<Expense | null>(null);
  const [aiQ, setAiQ] = useState("");
  const [aiA, setAiA] = useState<string | null>(null);

  function load() {
    api
      .listExpenses({ month, search, category, sort, min_amount: min, max_amount: max })
      .then(setRows);
  }
  useEffect(() => {
    load();
  }, [month, search, category, sort, min, max]);

  return (
    <>
      <div className="topbar">
        <h1>All expenses</h1>
        <MonthNav month={month} setMonth={setMonth} />
      </div>
      <div className="filters">
        <input aria-label="Search" placeholder="Search Starbucks, Uber, groceries…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id}>{c.name}</option>
          ))}
        </select>
        <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="highest">Highest amount</option>
          <option value="lowest">Lowest amount</option>
        </select>
        <input aria-label="Minimum amount" placeholder="Min $" value={min} onChange={(e) => setMin(e.target.value)} />
        <input aria-label="Maximum amount" placeholder="Max $" value={max} onChange={(e) => setMax(e.target.value)} />
        <button
          className="ghost"
          type="button"
          onClick={async () => {
            const csv = await api.exportCsv();
            const blob = new Blob([csv], { type: "text/csv" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "daybook.csv";
            a.click();
          }}
        >
          Export CSV
        </button>
      </div>
      <form
        className="composer"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!aiQ.trim()) return;
          const answer = await api.ask(aiQ, settings.timezone);
          setAiA(answer.explanation);
        }}
      >
        <input
          aria-label="Ask about your spending"
          placeholder="How much did I spend on coffee this month?"
          value={aiQ}
          onChange={(e) => setAiQ(e.target.value)}
        />
        <button className="ghost" type="submit">
          Ask
        </button>
      </form>
      {aiA ? <p className="bubble">{aiA}</p> : null}
      {rows === null ? (
        <div className="skeleton" style={{ height: 24 }} />
      ) : rows.length === 0 ? (
        <div className="empty">
          <h2>No expenses match.</h2>
          <p>Try another search or month.</p>
        </div>
      ) : (
        rows.map((row) => (
          <div className="expense-row" key={row.id}>
            <div className="meta">{prettyDate(row.date)}</div>
            <div>
              <div className="who">{row.merchant || row.description || "Expense"}</div>
              <div className="meta">
                {row.category}
                {row.description ? ` · ${row.description}` : ""}
              </div>
            </div>
            <div className="amt">{money(row.amount_cents)}</div>
            <div className="row-actions">
              <button className="icon-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              <button
                className="icon-btn"
                type="button"
                onClick={async () => {
                  await api.deleteExpense(row.id);
                  notify("Expense deleted.");
                  load();
                }}
              >
                Delete
              </button>
            </div>
          </div>
        ))
      )}
      {editing ? (
        <ExpenseForm
          categories={categories}
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            await api.updateExpense(editing.id, payload);
            notify("Expense updated.");
            setEditing(null);
            load();
          }}
        />
      ) : null}
    </>
  );
}

function InsightsPage({
  month,
  setMonth,
  settings,
}: {
  month: string;
  setMonth: (m: string) => void;
  settings: Settings;
}) {
  const [text, setText] = useState<string | null>(null);
  const [insights, setInsights] = useState<{ text: string }[]>([]);
  const [compare, setCompare] = useState<Dashboard["category_compare"]>([]);
  const [q, setQ] = useState("");
  const [a, setA] = useState<string | null>(null);

  useEffect(() => {
    api.insights(month).then((r) => {
      setText(r.narrative.text);
      setInsights(r.insights);
    });
    api.dashboard(month, settings.timezone).then((d) => setCompare(d.category_compare));
  }, [month, settings.timezone]);

  return (
    <>
      <div className="topbar">
        <h1>Insights</h1>
        <MonthNav month={month} setMonth={setMonth} />
      </div>
      <div className="assistant">
        <section>
          <h2>Monthly summary</h2>
          {text ? <pre className="bubble">{text}</pre> : <div className="skeleton" style={{ height: 120 }} />}
          <ul>
            {insights.map((i) => (
              <li key={i.text}>{i.text}</li>
            ))}
          </ul>
        </section>
        <section>
          <h2>Ask your journal</h2>
          <form
            className="composer"
            onSubmit={async (e) => {
              e.preventDefault();
              const answer = await api.ask(q, settings.timezone);
              setA(answer.explanation);
            }}
          >
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="What was my biggest category?" aria-label="Assistant question" />
            <button className="btn-primary" type="submit">
              Ask
            </button>
          </form>
          {a ? <div className="bubble">{a}</div> : null}
        </section>
      </div>
      <section style={{ marginTop: 32 }}>
        <h2>Category vs last month</h2>
        <div className="compare-row">
          <strong>Category</strong>
          <strong>Prev</strong>
          <strong>Now</strong>
          <strong>Change</strong>
        </div>
        {compare.map((row) => (
          <div className="compare-row" key={row.category}>
            <span>{row.category}</span>
            <span>{money(row.previous_cents)}</span>
            <span>{money(row.current_cents)}</span>
            <span className={row.delta_cents > 0 ? "delta up" : "delta down"}>
              {row.delta_cents > 0 ? "+" : ""}
              {money(row.delta_cents)}
              {row.percent ? ` (${row.percent}%)` : ""}
            </span>
          </div>
        ))}
      </section>
    </>
  );
}

function BudgetsPage({
  month,
  categories,
  notify,
}: {
  month: string;
  categories: Category[];
  notify: (t: string) => void;
}) {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof api.budgets>>>([]);
  const [category, setCategory] = useState("Food & Dining");
  const [amount, setAmount] = useState("500");

  function load() {
    api.budgets(month).then(setRows);
  }
  useEffect(load, [month]);

  return (
    <>
      <div className="topbar">
        <h1>Budgets</h1>
      </div>
      <p className="hint">Optional monthly caps by category. Spending is never blocked.</p>
      <form
        className="composer"
        onSubmit={async (e) => {
          e.preventDefault();
          await api.saveBudget({ category, month, amount: Number(amount) });
          notify(`Budget saved for ${category}.`);
          load();
        }}
      >
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Budget category">
          {categories.map((c) => (
            <option key={c.id}>{c.name}</option>
          ))}
        </select>
        <input aria-label="Budget amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <button className="btn-primary" type="submit">
          Save
        </button>
      </form>
      {rows.map((row) => (
        <div className="bar-row" key={row.id} style={{ marginTop: 12 }}>
          <span>{row.category}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${Math.min(row.percent, 100)}%` }} />
          </div>
          <span className="amt">
            {money(row.spent_cents)} / {money(row.amount_cents)}
          </span>
        </div>
      ))}
    </>
  );
}

function SubscriptionsPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof api.subscriptions>>>([]);
  useEffect(() => {
    api.subscriptions().then(setRows);
  }, []);
  return (
    <>
      <div className="topbar">
        <h1>Subscriptions</h1>
      </div>
      <p className="hint">Detected from similar merchant and amount on a repeating interval.</p>
      {rows.length === 0 ? (
        <div className="empty">
          <h2>No recurring expenses yet.</h2>
          <p>They appear after similar charges repeat.</p>
        </div>
      ) : (
        rows.map((row) => (
          <div className="expense-row" key={row.merchant + row.interval}>
            <div className="meta">{row.interval}</div>
            <div>
              <div className="who">{row.merchant}</div>
              <div className="meta">
                {row.category} · {row.count} charges · likely recurring
              </div>
            </div>
            <div className="amt">
              {row.monthly}/mo
              <div className="meta">{row.annual}/yr</div>
            </div>
            <div />
          </div>
        ))
      )}
    </>
  );
}

function SettingsPage({
  settings,
  setSettings,
  categories,
  setCategories,
  notify,
}: {
  settings: Settings;
  setSettings: (s: Settings) => void;
  categories: Category[];
  setCategories: (c: Category[]) => void;
  notify: (t: string) => void;
}) {
  const [draft, setDraft] = useState(settings);
  const [newCat, setNewCat] = useState("");
  const [rules, setRules] = useState<Awaited<ReturnType<typeof api.rules>>>([]);

  useEffect(() => {
    api.rules().then(setRules);
  }, []);

  return (
    <>
      <div className="topbar">
        <h1>Settings</h1>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="currency">Default currency</label>
          <input id="currency" value={draft.default_currency} onChange={(e) => setDraft({ ...draft, default_currency: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="tz">Timezone</label>
          <input id="tz" value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="week">Week starts</label>
          <select id="week" value={draft.week_start} onChange={(e) => setDraft({ ...draft, week_start: e.target.value })}>
            <option value="sunday">Sunday</option>
            <option value="monday">Monday</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="theme">Theme</label>
          <select id="theme" value={draft.theme} onChange={(e) => setDraft({ ...draft, theme: e.target.value })}>
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="ai">AI provider</label>
          <select id="ai" value={draft.ai_provider} onChange={(e) => setDraft({ ...draft, ai_provider: e.target.value })}>
            <option value="fallback">Built-in parser (no API)</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama (local)</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="auto">Auto-save parsed expenses</label>
          <select
            id="auto"
            value={draft.auto_save_ai ? "yes" : "no"}
            onChange={(e) => setDraft({ ...draft, auto_save_ai: e.target.value === "yes" })}
          >
            <option value="no">Off — confirm first</option>
            <option value="yes">On</option>
          </select>
        </div>
      </div>
      <p className="hint">
        API keys live in the backend `.env` only. OpenAI key {settings.has_openai_key ? "is set" : "is not set"}. Anthropic key{" "}
        {settings.has_anthropic_key ? "is set" : "is not set"}.
      </p>
      <button
        className="btn-primary"
        type="button"
        onClick={async () => {
          const saved = await api.saveSettings(draft);
          setSettings(saved);
          applyTheme(saved.theme);
          notify("Settings saved.");
        }}
      >
        Save settings
      </button>
      <h2 style={{ marginTop: 32 }}>Categories</h2>
      <form
        className="composer"
        onSubmit={async (e) => {
          e.preventDefault();
          const created = await api.addCategory(newCat);
          setCategories([...categories, created]);
          setNewCat("");
        }}
      >
        <input aria-label="New category" placeholder="Custom category" value={newCat} onChange={(e) => setNewCat(e.target.value)} />
        <button className="ghost" type="submit">
          Add
        </button>
      </form>
      <p className="hint">{categories.map((c) => c.name).join(" · ")}</p>
      <h2>Merchant rules</h2>
      {rules.map((r) => (
        <div className="expense-row" key={r.id}>
          <div className="who">{r.merchant_pattern}</div>
          <div className="meta">
            {r.preferred_category}
            {r.preferred_subcategory ? ` / ${r.preferred_subcategory}` : ""}
          </div>
          <div />
          <button
            className="icon-btn"
            type="button"
            onClick={async () => {
              await api.deleteRule(r.id);
              setRules(rules.filter((x) => x.id !== r.id));
            }}
          >
            Remove
          </button>
        </div>
      ))}
      <h2 style={{ marginTop: 32 }}>Backup</h2>
      <button
        className="ghost"
        type="button"
        onClick={async () => {
          const result = await api.backup();
          notify(`Backup saved to ${result.path}`);
        }}
      >
        Copy database backup
      </button>
    </>
  );
}

function ExpenseForm({
  categories,
  initial,
  onClose,
  onSave,
}: {
  categories: Category[];
  initial?: Partial<ParsedExpense & Expense> | null;
  onClose: () => void;
  onSave: (payload: Record<string, unknown>, force: boolean) => Promise<void>;
}) {
  const [amount, setAmount] = useState(String(initial?.amount ?? ""));
  const [date, setDate] = useState(String(initial?.date ?? new Date().toISOString().slice(0, 10)));
  const [category, setCategory] = useState(String(initial?.category ?? "Other"));
  const [merchant, setMerchant] = useState(initial?.merchant ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [payment, setPayment] = useState(initial?.payment_method ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [force, setForce] = useState(false);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form
        className="modal"
        onClick={(e) => e.stopPropagation()}
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            await onSave(
              {
                amount,
                date,
                category,
                merchant: merchant || null,
                description: description || null,
                payment_method: payment || null,
                notes: notes || null,
              },
              force,
            );
          } catch (err) {
            const e2 = err as { status?: number };
            if (e2.status === 409) {
              setForce(true);
              setError("This expense may already exist. Save anyway?");
            } else {
              setError("Could not save this expense.");
            }
          }
        }}
      >
        <h2>{initial && "id" in (initial as object) ? "Edit expense" : "Add expense"}</h2>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="amt">Amount</label>
            <input id="amt" required value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </div>
          <div className="field">
            <label htmlFor="dt">Date</label>
            <input id="dt" type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="cat">Category</label>
            <select id="cat" value={category} onChange={(e) => setCategory(e.target.value)}>
              {categories.map((c) => (
                <option key={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="merch">Merchant</label>
            <input id="merch" value={merchant} onChange={(e) => setMerchant(e.target.value)} />
          </div>
          <div className="field span-2">
            <label htmlFor="desc">Description</label>
            <input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pay">Payment method</label>
            <select id="pay" value={payment} onChange={(e) => setPayment(e.target.value)}>
              <option value="">Not specified</option>
              <option>Cash</option>
              <option>Debit</option>
              <option>Credit Card</option>
              <option>Apple Pay</option>
              <option>Venmo</option>
              <option>Other</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="notes">Notes</label>
            <input id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        {error ? <p className={force ? "warn" : "error"}>{error}</p> : null}
        <div className="actions" style={{ marginTop: 16 }}>
          <button className="btn-primary" type="submit">
            {force ? "Save anyway" : "Save"}
          </button>
          <button className="ghost" type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
