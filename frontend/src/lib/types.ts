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
  category_source: string | null;
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
  category_source: "keyword" | "ai" | "user" | null;
  category_confidence: number | null;
  category_reason: string | null;
  needs_check: boolean;
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
