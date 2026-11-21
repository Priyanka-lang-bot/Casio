"use client";

import { useCallback, useEffect, useState } from "react";
import { BasisBadge } from "@/components/basis-badge";
import { EntityList } from "@/components/entity-list";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { FREQUENCY_LABELS, formatMoney } from "@/lib/format";
import type { ProfileSummary } from "@/lib/types";

const ASSET_KINDS = {
  bank_account: "Bank account",
  savings: "Savings",
  emergency_fund: "Emergency fund",
  cash: "Cash",
  investment: "Investments",
  property: "Property",
  vehicle: "Vehicle",
  other: "Other",
};
const DEBT_KINDS = {
  credit_card: "Credit card",
  personal_loan: "Personal loan",
  home_loan: "Home loan",
  vehicle_loan: "Vehicle loan",
  education_loan: "Education loan",
  other: "Other",
};

function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "good" | "bad" }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${tone === "good" ? "text-success" : tone === "bad" ? "text-destructive" : ""}`}>
        {value}
      </p>
      {hint && <p className="text-muted-foreground mt-0.5 text-xs">{hint}</p>}
    </div>
  );
}

export function ProfileView() {
  const [s, setS] = useState<ProfileSummary | null>(null);
  const refresh = useCallback(() => {
    api<ProfileSummary>("/profile/summary").then((r) => r.ok && setS(r.data));
  }, []);
  useEffect(refresh, [refresh]);

  const cur = s?.currency ?? "INR";
  const m = (v: string | null) => formatMoney(v, cur);
  const freq = (i: Record<string, string | null>) => FREQUENCY_LABELS[i.frequency ?? "monthly"].toLowerCase();

  return (
    <>
      <PageHeader
        title="Financial Profile"
        description="Tell CASIO about your money in rough numbers. It's fine to estimate; you can change anything later. This is the starting point for your Money Model, goals and forecasts."
      />

      {s && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Your monthly picture <BasisBadge basis="estimate" />
            </CardTitle>
            <CardDescription>
              {s.is_empty
                ? "Add your income and regular costs below and CASIO will work out what's left each month."
                : "Worked out from what you entered below, converted to a per-month amount."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Money in per month" value={m(s.monthly_income)} />
            <Stat
              label="Money out per month"
              value={m(s.monthly_total_spending)}
              hint={`Fixed ${m(s.monthly_fixed_expenses)} · Variable ${m(s.monthly_variable_expenses)}${Number(s.monthly_debt_payments) ? ` · Debt ${m(s.monthly_debt_payments)}` : ""}`}
            />
            <Stat
              label="Left over each month"
              value={m(s.monthly_surplus)}
              tone={Number(s.monthly_surplus) < 0 ? "bad" : Number(s.monthly_surplus) > 0 ? "good" : undefined}
              hint="Money in − money out"
            />
            <Stat
              label="Net worth"
              value={m(s.net_worth)}
              tone={Number(s.net_worth) < 0 ? "bad" : undefined}
              hint="What you own − what you owe"
            />
            <Stat
              label="Emergency fund"
              value={m(s.emergency_fund)}
              hint={s.emergency_fund_months ? `Covers about ${s.emergency_fund_months} months of spending` : "Add one under “What you own”"}
            />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <EntityList
          title="Money coming in"
          description="Salary, freelance work, rent you receive, pension…"
          endpoint="/profile/income"
          noun="income"
          emptyText="No income added yet."
          onChange={refresh}
          fields={[
            { name: "name", label: "Name", type: "text", placeholder: "e.g. Salary" },
            { name: "amount", label: "Amount", type: "money", placeholder: "0.00" },
            { name: "frequency", label: "How often", type: "select", options: FREQUENCY_LABELS, defaultValue: "monthly" },
          ]}
          renderSummary={(i) => (
            <>
              <p className="font-medium">{i.name}</p>
              <p className="text-muted-foreground">
                {m(i.amount)} {freq(i)}
              </p>
            </>
          )}
        />
        <EntityList
          title="Regular costs"
          description="Fixed costs stay the same (rent, phone). Variable costs change (food, fuel)."
          endpoint="/profile/expenses"
          noun="cost"
          emptyText="No regular costs added yet."
          onChange={refresh}
          fields={[
            { name: "name", label: "Name", type: "text", placeholder: "e.g. Rent" },
            { name: "amount", label: "Amount", type: "money", placeholder: "0.00" },
            { name: "frequency", label: "How often", type: "select", options: FREQUENCY_LABELS, defaultValue: "monthly" },
            { name: "kind", label: "Type", type: "select", options: { fixed: "Fixed (same every time)", variable: "Variable (changes)" } },
          ]}
          renderSummary={(i) => (
            <>
              <p className="font-medium">{i.name}</p>
              <p className="text-muted-foreground">
                {m(i.amount)} {freq(i)} · {i.kind === "fixed" ? "Fixed" : "Variable"}
              </p>
            </>
          )}
        />
        <EntityList
          title="What you own"
          description="Money in the bank, savings, an emergency fund, investments, property…"
          endpoint="/profile/assets"
          noun="item"
          emptyText="Nothing added yet."
          onChange={refresh}
          fields={[
            { name: "name", label: "Name", type: "text", placeholder: "e.g. HDFC savings account" },
            { name: "kind", label: "Type", type: "select", options: ASSET_KINDS },
            { name: "value", label: "Current value", type: "money", placeholder: "0.00" },
          ]}
          renderSummary={(i) => (
            <>
              <p className="font-medium">{i.name}</p>
              <p className="text-muted-foreground">
                {m(i.value)} · {ASSET_KINDS[i.kind as keyof typeof ASSET_KINDS]}
              </p>
            </>
          )}
        />
        <EntityList
          title="What you owe"
          description="Credit cards, loans and other debts."
          endpoint="/profile/liabilities"
          noun="debt"
          emptyText="No debts added. Great if that's true!"
          onChange={refresh}
          fields={[
            { name: "name", label: "Name", type: "text", placeholder: "e.g. Car loan" },
            { name: "kind", label: "Type", type: "select", options: DEBT_KINDS },
            { name: "balance", label: "Amount still owed", type: "money", placeholder: "0.00" },
            { name: "monthly_payment", label: "Monthly payment", type: "money", optional: true, placeholder: "0.00" },
            { name: "interest_rate", label: "Interest rate per year (%)", type: "percent", optional: true, placeholder: "e.g. 12.5" },
          ]}
          renderSummary={(i) => (
            <>
              <p className="font-medium">{i.name}</p>
              <p className="text-muted-foreground">
                {m(i.balance)} owed{i.monthly_payment ? ` · ${m(i.monthly_payment)}/month` : ""}
                {i.interest_rate ? ` · ${Number(i.interest_rate)}% a year` : ""}
              </p>
            </>
          )}
        />
      </div>
    </>
  );
}
