// Shapes of data returned by the backend. Money is always a string.

export type Category = { id: string; name: string; kind: "income" | "expense" | "transfer"; is_custom: boolean };

export type Transaction = {
  id: string;
  type: "income" | "expense" | "transfer";
  amount: string;
  currency: string;
  occurred_on: string;
  description: string;
  notes: string | null;
  category_id: string | null;
  category_name: string | null;
  source: string;
  import_batch_id: string | null;
  category_source: "user" | "rule" | "ai" | "keyword" | null;
  category_confidence: number | null;
  category_reason: string | null;
  rule_id: string | null;
  merchant: string | null;
};

export type ProfileSummary = {
  basis: "user_estimate";
  currency: string;
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

export type Overview = {
  currency: string;
  month: string;
  has_transactions: boolean;
  actual: {
    basis: "actual";
    month_income: string;
    month_expenses: string;
    month_net: string;
    savings_rate_percent: string | null;
    tracked_balance: string;
  };
  spending_by_category: { category: string; amount: string }[];
  trend: { month: string; income: string; expenses: string }[];
  recent_transactions: Transaction[];
  plan: ProfileSummary;
};

export type ImportRow = {
  id: string;
  position: number;
  row_number: number | null;
  raw_text: string;
  occurred_on: string | null;
  description: string;
  merchant: string | null;
  amount: string | null;
  type: "income" | "expense" | null;
  balance_after: string | null;
  category_id: string | null;
  category_name: string | null;
  category_source: "keyword" | "ai" | "user" | "rule" | null;
  category_confidence: number | null;
  category_reason: string | null;
  needs_check: boolean;
  rule_id: string | null;
  problems: string[];
  duplicate_kind: "exact" | "possible" | "in_file" | null;
  duplicate_note: string | null;
  include: boolean;
  edited: boolean;
};

export type ImportBatch = {
  id: string;
  source_type: "csv" | "pdf" | "sms";
  original_filename: string | null;
  status: "processing" | "needs_review" | "completed" | "failed" | "cancelled";
  rows_found: number;
  rows_imported: number;
  rows_duplicate: number;
  rows_failed: number;
  warnings: string[] | null;
  ai_status: "used" | "not_configured" | "failed" | "not_needed" | null;
  created_at: string;
  completed_at: string | null;
};

export type ImportDetail = ImportBatch & {
  errors: { row_number: number | null; raw_text: string | null; message: string }[];
  rows: ImportRow[];
};

// ---- Learned rules ----
export type Priority = "high" | "normal" | "low";

export type Rule = {
  id: string;
  category_id: string;
  category_name: string;
  match_type: "merchant" | "contains";
  pattern: string;
  applies_to: "income" | "expense";
  priority: Priority;
  active: boolean;
  times_applied: number;
  times_overridden: number;
  confidence: number;
  weak: boolean;
  currently_applied: number;
  last_applied_at: string | null;
  created_at: string;
  conflicts: { rule_id: string; pattern: string; match_type: string; category_name: string; this_wins: boolean; transactions: number }[];
};

export type RuleSave = { rule: Rule; changed_transactions: number; changed_import_rows: number; replaced: boolean };

export type RulePreview = {
  tx_type: "income" | "expense";
  merchant_key: string | null;
  match_type: "merchant" | "contains";
  pattern: string;
  suggested_word: string;
  pattern_problem: string | null;
  category_id: string;
  category_name: string;
  matching_past: number;
  examples: { description: string; occurred_on: string; amount: string; category_name: string | null }[];
  matching_in_import: number;
  existing_rule: { id: string; category_name: string; same_category: boolean } | null;
  overlaps: { id: string; match_type: string; pattern: string; category_name: string; wins: boolean }[];
  recommendation: "always" | "once";
  reason: string;
  prior_corrections: number;
};

export type Correction = {
  id: string;
  description: string;
  from_category: string | null;
  to_category: string | null;
  from_source: string | null;
  made_rule: boolean;
  created_at: string;
};

// ---- Subscriptions and recurring payments ----
export type Recurring = {
  id: string;
  name: string;
  kind: "subscription" | "bill" | "other";
  category_name: string | null;
  frequency: "weekly" | "fortnightly" | "monthly" | "quarterly" | "yearly";
  amount: string;
  average_amount: string;
  amount_varies: boolean;
  monthly_cost: string;
  yearly_cost: string;
  first_paid_on: string;
  last_paid_on: string;
  next_expected_on: string | null;
  occurrences: number;
  confidence: number;
  charges: { date: string; amount: string }[];
  price_changes: { date: string; old: string; new: string }[];
  status: "active" | "cancelled" | "not_recurring";
  state: "active" | "overdue" | "cancelled" | "not_recurring";
  usage: "unknown" | "using" | "rarely" | "not_using";
  usage_confirmed_at: string | null;
  explanation: string;
  manual?: boolean;
};

export type RecurringAlert = { id: string; recurring_payment_id: string; kind: string; message: string; created_at: string };

export type RecurringPage = {
  as_of: string;
  currency: string;
  summary: {
    basis: "actual";
    active_count: number;
    monthly_total: string;
    yearly_total: string;
    subscriptions_monthly: string;
    bills_monthly: string;
    not_using_yearly: string;
    unknown_usage_count: number;
  };
  items: Recurring[];
  alerts: RecurringAlert[];
};
