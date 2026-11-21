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
