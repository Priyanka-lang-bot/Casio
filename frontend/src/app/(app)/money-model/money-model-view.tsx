"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Stat } from "@/components/stat";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { FREQUENCY_LABELS, formatDate, formatMoney, formatMonth } from "@/lib/format";
import type { MoneyModel } from "@/lib/planning-types";

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 py-1.5 text-sm ${strong ? "border-t pt-2 font-semibold" : ""}`}>
      <span className={strong ? "" : "text-muted-foreground"}>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

export function MoneyModelView() {
  const [m, setM] = useState<MoneyModel | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<MoneyModel>("/money-model").then((r) => (r.ok ? setM(r.data) : setError(r.message)));
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!m) return <p className="text-muted-foreground py-10 text-center text-sm">Building your money model…</p>;
  const c = m.currency;
  const e = m.estimate;
  const a = m.actual;
  const empty = !m.has_actuals && e.is_empty;
  const chart = m.forecast.months.map((x) => ({ month: formatMonth(x.month), Savings: Number(x.savings) }));

  return (
    <>
      <PageHeader
        title="Living Money Model"
        description="One picture of your money that updates whenever you add transactions, fix a category or change your profile. Every number says where it comes from."
      />
      <div className="text-muted-foreground mb-6 flex flex-wrap items-center gap-2 text-xs">
        <BasisBadge basis="actual" /> from your transactions
        <BasisBadge basis="estimate" /> what you told CASIO
        <Badge variant="outline" className="border-primary/40">Planned</Badge> your budgets and goals
        <BasisBadge basis="forecast" /> a projection, not a promise
      </div>

      {empty && (
        <div className="mb-6">
          <Alert kind="info">
            Your model is empty. <Link href="/import" className="underline">Import a statement</Link> or fill in your{" "}
            <Link href="/profile" className="underline">Financial Profile</Link> to bring it to life.
          </Alert>
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Usual monthly income" value={formatMoney(m.monthly_income, c)} badge={<BasisBadge basis={m.plan_basis === "actual" ? "actual" : "estimate"} />} />
        <Stat label="Usual monthly spending" value={formatMoney(m.monthly_spending, c)} badge={<BasisBadge basis={m.plan_basis === "actual" ? "actual" : "estimate"} />} />
        <Stat label="Left over each month" value={formatMoney(m.monthly_surplus, c)} tone={Number(m.monthly_surplus) < 0 ? "bad" : "good"} sub={`${formatMoney(m.free_after_goals, c)} after goal savings`} />
        <Stat label="Net worth" value={formatMoney(e.net_worth, c)} badge={<BasisBadge basis="estimate" />} sub="assets minus debts" />
      </div>

      {m.gaps.length > 0 && (
        <div className="mb-6 space-y-2">
          {m.gaps.map((g) => <Alert key={g} kind="info">{g.replace(/(\d+\.\d{2})/g, (x) => formatMoney(x, c))}</Alert>)}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">What really happened <BasisBadge basis="actual" /></CardTitle>
            <CardDescription>
              {m.has_actuals ? `Average of ${m.history_months.map(formatMonth).join(", ")}.` : "No transactions yet."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Row label="Usual income" value={formatMoney(a.usual_monthly_income, c)} />
            <Row label="Usual spending" value={formatMoney(a.usual_monthly_spending, c)} />
            {a.usual_spending_by_category.slice(0, 6).map((x) => <Row key={x.category} label={`· ${x.category}`} value={formatMoney(x.amount, c)} />)}
            <Row label={`${formatMonth(a.this_month)} so far: in / out`} value={`${formatMoney(a.this_month_income, c)} / ${formatMoney(a.this_month_spending, c)}`} strong />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">What you told CASIO <BasisBadge basis="estimate" /></CardTitle>
            <CardDescription>From your <Link href="/profile" className="underline">Financial Profile</Link>.</CardDescription>
          </CardHeader>
          <CardContent>
            <Row label="Income" value={formatMoney(e.monthly_income, c)} />
            <Row label="Fixed costs" value={formatMoney(e.monthly_fixed_expenses, c)} />
            <Row label="Variable costs" value={formatMoney(e.monthly_variable_expenses, c)} />
            <Row label="Debt payments" value={formatMoney(e.monthly_debt_payments, c)} />
            <Row label="Savings" value={formatMoney(e.savings, c)} />
            <Row label="Emergency fund" value={`${formatMoney(e.emergency_fund, c)}${m.emergency_fund_months ? ` (${m.emergency_fund_months} months)` : ""}`} />
            <Row label="Assets / debts" value={`${formatMoney(e.total_assets, c)} / ${formatMoney(e.total_liabilities, c)}`} strong />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">Your plan <Badge variant="outline" className="border-primary/40">Planned</Badge></CardTitle>
          </CardHeader>
          <CardContent>
            <Row label={`Budgets (${m.planned.budget_count})`} value={formatMoney(m.planned.budgets_total, c)} />
            <Row label={`Goal savings (${m.planned.active_goals} goals)`} value={formatMoney(m.planned.goal_contributions, c)} />
            <Row label="Regular commitments" value={formatMoney(m.commitments.monthly_total, c)} />
            <p className="text-muted-foreground pt-2 text-xs">
              Manage in <Link href="/budgets" className="underline">Budgets</Link>, <Link href="/goals" className="underline">Goals</Link> and{" "}
              <Link href="/subscriptions" className="underline">Subscriptions</Link>.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Regular commitments <BasisBadge basis="actual" /></CardTitle>
            <CardDescription>Payments CASIO saw repeating. Next dates are forecasts.</CardDescription>
          </CardHeader>
          <CardContent>
            {m.commitments.items.length === 0 ? (
              <p className="text-muted-foreground text-sm">None found yet.</p>
            ) : (
              m.commitments.items.slice(0, 8).map((x) => (
                <Row key={x.name} label={`${x.name} · ${FREQUENCY_LABELS[x.frequency] ?? x.frequency}${x.next_expected_on ? ` · next ~${formatDate(x.next_expected_on)}` : ""}`} value={formatMoney(x.amount, c)} />
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">Savings forecast <BasisBadge basis="forecast" /></CardTitle>
          <CardDescription>
            Starting from {formatMoney(m.forecast.starting_savings, c)} saved and changing by {formatMoney(m.forecast.monthly_change, c)} a month. Real months will differ.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" fontSize={12} />
              <YAxis fontSize={12} width={70} tickFormatter={(v) => formatMoney(v, c).replace(/\.00$/, "")} />
              <Tooltip formatter={(v) => formatMoney(Number(v), c)} />
              <Line isAnimationActive={false} type="monotone" dataKey="Savings" stroke="var(--color-primary)" strokeWidth={2} strokeDasharray="6 3" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {m.snapshots.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Month by month</CardTitle>
            <CardDescription>A snapshot of your model is kept each month so you can see how things change.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead className="text-muted-foreground text-left">
                <tr><th className="py-1 font-medium">Month</th><th className="font-medium">Usual income</th><th className="font-medium">Usual spending</th><th className="font-medium">Left over</th><th className="font-medium">Net worth</th></tr>
              </thead>
              <tbody>
                {m.snapshots.map((s) => (
                  <tr key={s.month} className="border-t tabular-nums">
                    <td className="py-1.5">{formatMonth(s.month)}</td>
                    <td>{formatMoney(s.monthly_income, c)}</td>
                    <td>{formatMoney(s.monthly_spending, c)}</td>
                    <td>{formatMoney(s.monthly_surplus, c)}</td>
                    <td>{formatMoney(s.net_worth, c)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
