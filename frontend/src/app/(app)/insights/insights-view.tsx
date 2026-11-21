"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowDownRightIcon, ArrowUpRightIcon, BellIcon, CalculatorIcon } from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { NudgeList } from "@/components/nudge-list";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import type { MoneyModel, Report } from "@/lib/planning-types";
import type { RecurringAlert } from "@/lib/types";

function lastFullMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Spending Insights: what changed, where money usually goes, and what CASIO
// noticed. Every figure comes from the backend's calculations on your data.
export function InsightsView() {
  const [model, setModel] = useState<MoneyModel | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [alerts, setAlerts] = useState<RecurringAlert[]>([]);
  const [error, setError] = useState("");
  const month = lastFullMonth();

  useEffect(() => {
    api<MoneyModel>("/money-model").then((r) => (r.ok ? setModel(r.data) : setError(r.message)));
    api<Report>(`/reports/${month}`).then((r) => r.ok && setReport(r.data));
    api<RecurringAlert[]>("/subscriptions/alerts?limit=5").then((r) => r.ok && setAlerts(r.data));
  }, [month]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!model) return <p className="text-muted-foreground py-10 text-center text-sm">Loading your insights…</p>;

  const c = model.currency;
  const usual = model.actual.usual_spending_by_category;
  const usualTotal = Number(model.actual.usual_monthly_spending) || 1;
  const changes = (report?.categories ?? []).filter((x) => Number(x.change) !== 0).sort((a, b) => Math.abs(Number(b.change)) - Math.abs(Number(a.change))).slice(0, 6);
  const maxChange = Math.max(...changes.map((x) => Math.abs(Number(x.change))), 1);

  return (
    <>
      <PageHeader title="Spending Insights" description="What changed, where your money usually goes, and what CASIO noticed. All worked out from your own transactions." />

      {!model.has_actuals && (
        <Card className="mb-6 border-primary/30 bg-primary/5">
          <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm">Insights appear after one full month of transactions. Import a statement to get started.</p>
            <Button asChild>
              <Link href="/import">Import a statement</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {formatMonth(month)} compared with {report ? formatMonth(report.previous.month) : "the month before"} <BasisBadge basis="actual" />
            </CardTitle>
            <CardDescription>
              {report && Number(report.previous.spending) > 0
                ? `Spending ${formatMoney(report.summary.spending, c)} vs ${formatMoney(report.previous.spending, c)}. Categories with the biggest change:`
                : "Biggest changes by category."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {changes.length === 0 ? (
              <p className="text-muted-foreground text-sm">Not enough data to compare yet.</p>
            ) : (
              <ul className="space-y-3">
                {changes.map((x) => {
                  const up = Number(x.change) > 0;
                  return (
                    <li key={x.category}>
                      <div className="flex items-center justify-between gap-2 text-sm">
                        <span className="flex items-center gap-1.5 font-medium">
                          {up ? <ArrowUpRightIcon className="text-destructive size-4" aria-hidden="true" /> : <ArrowDownRightIcon className="text-success size-4" aria-hidden="true" />}
                          {x.category}
                        </span>
                        <span className={`tabular-nums ${up ? "text-destructive" : "text-success"}`}>
                          {up ? "+" : "−"}
                          {formatMoney(Math.abs(Number(x.change)), c)}
                          <span className="sr-only">{up ? " more" : " less"}</span>
                        </span>
                      </div>
                      <div className="bg-muted mt-1 h-1.5 overflow-hidden rounded-full" aria-hidden="true">
                        <div className={`h-full rounded-full ${up ? "bg-destructive/70" : "bg-success/70"}`} style={{ width: `${(Math.abs(Number(x.change)) / maxChange) * 100}%` }} />
                      </div>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        {formatMoney(x.previous, c)} → {formatMoney(x.amount, c)}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
            {report && report.highlights.length > 0 && (
              <ul className="text-muted-foreground mt-4 list-disc space-y-1 border-t pt-4 pl-5 text-sm">
                {report.highlights.slice(1, 5).map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Where your money usually goes <BasisBadge basis="actual" />
            </CardTitle>
            <CardDescription>
              Your usual month: about {formatMoney(model.actual.usual_monthly_spending, c)} spent out of {formatMoney(model.actual.usual_monthly_income, c)} income.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5">
              {usual.slice(0, 8).map((x) => {
                const pct = (Number(x.amount) / usualTotal) * 100;
                return (
                  <li key={x.category}>
                    <div className="flex justify-between gap-2 text-sm">
                      <span>{x.category}</span>
                      <span className="tabular-nums">
                        {formatMoney(x.amount, c)} <span className="text-muted-foreground text-xs">· {pct.toFixed(0)}%</span>
                      </span>
                    </div>
                    <div className="bg-muted mt-1 h-1.5 overflow-hidden rounded-full" aria-hidden="true">
                      <div className="bg-primary/70 h-full rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>What CASIO noticed</CardTitle>
            <CardDescription>Checked again each time you open this page.</CardDescription>
          </CardHeader>
          <CardContent>
            <NudgeList limit={8} emptyText="Nothing needs your attention right now." />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BellIcon className="size-4" aria-hidden="true" /> Regular payment changes
            </CardTitle>
            <CardDescription>Price rises, new and missed payments found in your statements.</CardDescription>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <p className="text-muted-foreground text-sm">No changes to your regular payments.</p>
            ) : (
              <ul className="list-disc space-y-1.5 pl-5 text-sm">
                {alerts.map((a) => (
                  <li key={a.id}>{a.message}</li>
                ))}
              </ul>
            )}
            <Button asChild variant="outline" size="sm" className="mt-4">
              <Link href="/subscriptions">Open Subscriptions</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6 bg-muted/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalculatorIcon className="size-4" aria-hidden="true" /> How these are worked out
          </CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground space-y-1.5 text-sm">
          <p>
            <strong className="text-foreground">Usual month</strong> = the average of your last {model.history_months?.length || 3} full months of recorded transactions.
          </p>
          <p>
            <strong className="text-foreground">Change</strong> = what you spent in a category last month minus the month before.
          </p>
          <p>
            <strong className="text-foreground">Spending</strong> counts money out only. Transfers to your own savings or investments are not spending.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
