// Shapes for budgets, goals, money model, what-if, nudges, reports and coach.
// Money is always a string, exactly as the backend sends it.

export type BudgetItem = {
  id: string;
  category_id: string;
  category_name: string;
  amount: string;
  spent: string;
  remaining: string;
  percent_used: string;
  projected: string;
  projected_basis: "forecast" | "actual";
  usual_spend: string | null;
  state: "ok" | "near" | "over" | "on_pace_to_exceed";
};

export type BudgetPage = {
  currency: string;
  month: string;
  is_current_month: boolean;
  days_in_month: number;
  days_elapsed: number;
  items: BudgetItem[];
  unbudgeted: { category_id: string | null; category_name: string; spent: string }[];
  suggestions: { category_id: string; category_name: string; usual_spend: string; suggested_amount: string }[];
  total_budget: string;
  total_spent: string;
  total_remaining: string;
};

export type GoalState = "achieved" | "paused" | "no_date" | "past_due" | "no_plan" | "on_track" | "behind";

export type Goal = {
  id: string;
  name: string;
  kind: string;
  target_amount: string;
  saved_amount: string;
  target_date: string | null;
  priority: number;
  status: "active" | "achieved" | "paused";
  remaining: string;
  progress_percent: string;
  months_left: number | null;
  needed_per_month: string | null;
  monthly_contribution: string | null;
  months_to_finish: number | null;
  projected_finish: string | null;
  state: GoalState;
};

export type GoalPage = {
  currency: string;
  goals: Goal[];
  totals: { target: string; saved: string; monthly_contributions: string; monthly_surplus: string; plan_basis: string };
  suggested_emergency_fund: string | null;
};

export type MoneyModel = {
  as_of: string;
  currency: string;
  has_actuals: boolean;
  history_months: string[];
  estimate: {
    monthly_income: string;
    monthly_fixed_expenses: string;
    monthly_variable_expenses: string;
    monthly_debt_payments: string;
    monthly_total_spending: string;
    monthly_surplus: string;
    total_assets: string;
    total_liabilities: string;
    net_worth: string;
    savings: string;
    emergency_fund: string;
    emergency_fund_months: string | null;
    is_empty: boolean;
  };
  actual: {
    usual_monthly_income: string;
    usual_monthly_spending: string;
    usual_spending_by_category: { category: string; amount: string }[];
    this_month: string;
    this_month_income: string;
    this_month_spending: string;
  };
  planned: { budgets_total: string; budget_count: number; goal_contributions: string; active_goals: number };
  commitments: {
    monthly_total: string;
    items: { name: string; kind: string; frequency: string; amount: string; monthly: string; next_expected_on: string | null }[];
  };
  plan_basis: "actual" | "user_estimate";
  monthly_income: string;
  monthly_spending: string;
  monthly_surplus: string;
  free_after_goals: string;
  emergency_fund_months: string | null;
  forecast: { starting_savings: string; monthly_change: string; months: { month: string; savings: string }[] };
  gaps: string[];
  snapshots: ({ month: string } & Record<string, string>)[];
};

export type Change = {
  type: "income_change" | "category_change" | "spending_change" | "new_expense" | "extra_saving" | "one_time_expense";
  category?: string;
  label?: string;
  percent?: number;
  amount?: number;
};

export type SimResult = {
  currency: string;
  plan_basis: string;
  has_data: boolean;
  changes: { type: string; label: string; before: string; after: string }[];
  problems: string[];
  baseline: { income: string; spending: string; surplus: string; savings_rate: string | null };
  scenario: { income: string; spending: string; surplus: string; savings_rate: string | null; extra_saving: string; one_time_expense: string };
  difference: { income: string; spending: string; surplus: string; after_12_months: string };
  projection: { month: string; baseline: string; scenario: string }[];
  goals: {
    id: string;
    name: string;
    target_amount: string;
    saved_amount: string;
    target_date: string | null;
    baseline: { monthly: string; finish: string | null; months: number | null; state: string };
    scenario: { monthly: string; finish: string | null; months: number | null; state: string };
    months_sooner_or_later: number | null;
  }[];
  explanation: string[];
  disclaimer: string;
  parsed_by?: "ai" | "rules";
  parsed_changes?: Change[];
};

export type Nudge = {
  id: string;
  kind: string;
  severity: "info" | "warning" | "critical" | "good";
  title: string;
  message: string;
  link: string | null;
  created_at: string;
};

export type ReportList = { months: { month: string; generated_at: string | null }[]; ai: "ready" | "not_configured" };

export type Report = {
  month: string;
  currency: string;
  summary: { income: string; spending: string; net: string; savings_rate: string | null; transactions: number };
  previous: { month: string; income: string; spending: string; net: string; savings_rate: string | null };
  categories: { category: string; amount: string; previous: string; change: string; change_percent: string | null; share_percent: string | null }[];
  budgets: { items: BudgetItem[]; total_budget: string; total_spent: string };
  goals: { name: string; saved_amount: string; target_amount: string; added_this_month: string; progress_percent: string; state: string }[];
  subscriptions: { monthly_total: string; count: number; price_rises: { name: string; old: string; new: string; date: string }[]; new: string[] };
  largest_expenses: { date: string; description: string; amount: string; category: string | null }[];
  highlights: string[];
  suggestions: string[];
  narrative: string;
  narrative_source: "ai" | "template";
  generated_at: string;
};

export type CoachMsg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta: { source?: "ai" | "helper" | "guardrail"; tools?: string[]; blocked?: boolean };
  created_at: string;
};
