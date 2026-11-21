"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowDownIcon, ArrowUpIcon, PlusIcon, UserRoundIcon } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatDate, formatMoney, formatMonth } from "@/lib/format";
import type { Overview } from "@/lib/types";

function Metric({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" }) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <p className="text-muted-foreground text-sm">{label}</p>
        <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone === "good" ? "text-success" : tone === "bad" ? "text-destructive" : ""}`}>
          {value}
        </p>
        {sub && <p className="text-muted-foreground mt-1 text-xs">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function OverviewView({ firstName }: { firstName: string }) {
  const [month, setMonth] = useState("");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Overview>(`/overview${month ? `?month=${month}` : ""}`).then((r) => {
      if (r.ok) setData(r.data);
      else setError(r.message);
    });
  }, [month]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-muted-foreground py-10 text-center text-sm">Loading your overview…</p>;

  const c = data.currency;
  const a = data.actual;
  const p = data.plan;
  const net = Number(a.month_net);
  const chart = data.trend.map((t) => ({ month: formatMonth(t.month), Income: Number(t.income), Expenses: Number(t.expenses) }));
  const maxCat = Math.max(...data.spending_by_category.map((x) => Number(x.amount)), 1);

  return (
    <>
      <PageHeader
        title={`Hi ${firstName} 👋`}
        description="Here's where your money stands."
        action={
          <div className="flex items-center gap-2">
            <label htmlFor="ov-month" className="text-muted-foreground text-sm">
              Month
            </label>
            <Input id="ov-month" type="month" className="w-full sm:w-44" value={month || data.month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </div>
        }
      />

      {!data.has_transactions && (
        <Card className="mb-6 border-primary/30 bg-primary/5">
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium">Let&apos;s get started</p>
              <p className="text-muted-foreground text-sm">
                Add a few transactions and fill in your financial profile. Your numbers will appear here.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/transactions">
                  <PlusIcon /> Add a transaction
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/profile">
                  <UserRoundIcon /> Fill in profile
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="mb-2 flex items-center gap-2">
        <h2 className="font-semibold">{formatMonth(data.month)}</h2>
        <BasisBadge basis="actual" />
      </div>
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Money in" value={formatMoney(a.month_income, c)} />
        <Metric label="Money out" value={formatMoney(a.month_expenses, c)} />
        <Metric
          label="Left over"
          value={formatMoney(a.month_net, c)}
          tone={net < 0 ? "bad" : net > 0 ? "good" : undefined}
          sub={a.savings_rate_percent !== null ? `You kept ${a.savings_rate_percent}% of what came in` : "Money in − money out"}
        />
        <Metric
          label="Tracked balance"
          value={formatMoney(a.tracked_balance, c)}
          sub="All recorded income − all recorded expenses"
        />
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Last 6 months</CardTitle>
            <CardDescription>Money in vs money out each month</CardDescription>
          </CardHeader>
          <CardContent>
            {data.has_transactions ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis tickLine={false} axisLine={false} fontSize={12} width={70} tickFormatter={(v) => formatMoney(v, c).replace(/\.00$/, "")} />
                    <Tooltip formatter={(v) => formatMoney(Number(v), c)} />
                    <Legend />
                    <Bar dataKey="Income" fill="var(--success)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Expenses" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-muted-foreground py-16 text-center text-sm">Your chart will appear once you add transactions.</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Where your money went</CardTitle>
            <CardDescription>Spending by category in {formatMonth(data.month)}</CardDescription>
          </CardHeader>
          <CardContent>
            {data.spending_by_category.length === 0 ? (
              <p className="text-muted-foreground py-10 text-center text-sm">No spending recorded this month.</p>
            ) : (
              <ul className="space-y-3">
                {data.spending_by_category.map((x) => (
                  <li key={x.category}>
                    <div className="flex justify-between text-sm">
                      <span>{x.category}</span>
                      <span className="font-medium tabular-nums">{formatMoney(x.amount, c)}</span>
                    </div>
                    <div className="bg-muted mt-1 h-2 rounded-full">
                      <div className="bg-primary h-2 rounded-full" style={{ width: `${(Number(x.amount) / maxCat) * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent transactions</CardTitle>
            <CardAction>
              <Button asChild variant="link" size="sm">
                <Link href="/transactions">See all</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {data.recent_transactions.length === 0 ? (
              <p className="text-muted-foreground text-sm">Nothing yet.</p>
            ) : (
              <ul className="divide-y">
                {data.recent_transactions.map((t) => (
                  <li key={t.id} className="flex items-center gap-3 py-2.5">
                    <span
                      className={`flex size-8 shrink-0 items-center justify-center rounded-full ${t.type === "income" ? "bg-success/10 text-success" : "bg-muted"}`}
                    >
                      {t.type === "income" ? <ArrowDownIcon className="size-4" /> : <ArrowUpIcon className="size-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{t.description}</p>
                      <p className="text-muted-foreground text-xs">
                        {formatDate(t.occurred_on)} · {t.category_name ?? "No category"}
                      </p>
                    </div>
                    <span className={`text-sm font-semibold tabular-nums ${t.type === "income" ? "text-success" : ""}`}>
                      {t.type === "income" ? "+" : "−"}
                      {formatMoney(t.amount, t.currency)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Your plan <BasisBadge basis="estimate" />
            </CardTitle>
            <CardDescription>From your Financial Profile, not from transactions.</CardDescription>
            <CardAction>
              <Button asChild variant="link" size="sm">
                <Link href="/profile">Edit</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {p.is_empty ? (
              <p className="text-muted-foreground text-sm">
                Add your usual income and costs in your{" "}
                <Link href="/profile" className="text-primary underline">
                  Financial Profile
                </Link>{" "}
                to see your monthly plan and net worth here.
              </p>
            ) : (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <dt className="text-muted-foreground">Expected money in / month</dt>
                <dd className="text-right font-medium tabular-nums">{formatMoney(p.monthly_income, c)}</dd>
                <dt className="text-muted-foreground">Expected money out / month</dt>
                <dd className="text-right font-medium tabular-nums">{formatMoney(p.monthly_total_spending, c)}</dd>
                <dt className="text-muted-foreground">Expected left over / month</dt>
                <dd className={`text-right font-medium tabular-nums ${Number(p.monthly_surplus) < 0 ? "text-destructive" : ""}`}>
                  {formatMoney(p.monthly_surplus, c)}
                </dd>
                <dt className="text-muted-foreground">Net worth</dt>
                <dd className="text-right font-medium tabular-nums">{formatMoney(p.net_worth, c)}</dd>
                <dt className="text-muted-foreground">Savings</dt>
                <dd className="text-right font-medium tabular-nums">{formatMoney(p.savings, c)}</dd>
                <dt className="text-muted-foreground">Emergency fund covers</dt>
                <dd className="text-right font-medium tabular-nums">
                  {p.emergency_fund_months ? `${p.emergency_fund_months} months` : "—"}
                </dd>
              </dl>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
