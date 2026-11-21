"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DownloadIcon, FileTextIcon, PrinterIcon, RefreshCwIcon, SparklesIcon } from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Stat } from "@/components/stat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatDate, formatMoney, formatMonth } from "@/lib/format";
import type { Report, ReportList } from "@/lib/planning-types";

// Builds a spreadsheet-friendly CSV of the report in the browser. Amounts are
// written exactly as the backend calculated them.
function downloadCsv(r: Report) {
  const rows: (string | number | null)[][] = [
    ["CASIO monthly report", r.month],
    [],
    ["Summary", "This month", "Previous month"],
    ["Money in", r.summary.income, r.previous.income],
    ["Money out", r.summary.spending, r.previous.spending],
    ["Left over", r.summary.net, r.previous.net],
    ["Savings rate %", r.summary.savings_rate, r.previous.savings_rate],
    [],
    ["Category", "Amount", "Previous month", "Change", "Share %"],
    ...r.categories.map((c) => [c.category, c.amount, c.previous, c.change, c.share_percent]),
    [],
    ["Budget", "Limit", "Spent", "Left"],
    ...r.budgets.items.map((b) => [b.category_name, b.amount, b.spent, b.remaining]),
    [],
    ["Goal", "Saved", "Target", "Added this month", "Progress %"],
    ...r.goals.map((g) => [g.name, g.saved_amount, g.target_amount, g.added_this_month, g.progress_percent]),
    [],
    ["Largest expenses", "Date", "Amount", "Category"],
    ...r.largest_expenses.map((e) => [e.description, e.date, e.amount, e.category]),
  ];
  const esc = (v: string | number | null) => {
    let t = v === null || v === undefined ? "" : String(v);
    if (/^[=+@\t\r]/.test(t) || (/^-/.test(t) && Number.isNaN(Number(t)))) t = `'${t}`; // never a spreadsheet formula
    return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
  };
  const blob = new Blob([rows.map((row) => row.map(esc).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `casio-report-${r.month}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function ReportsView() {
  const [list, setList] = useState<ReportList | null>(null);
  const [month, setMonth] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<ReportList>("/reports").then((r) => {
      if (!r.ok) return setError(r.message);
      setList(r.data);
      // Default to the last complete month if there is one.
      const ms = r.data.months.map((m) => m.month);
      setMonth(ms[1] ?? ms[0] ?? "");
    });
  }, []);

  useEffect(() => {
    if (!month) return;
    api<Report>(`/reports/${month}`).then((r) => {
      if (r.ok) setReport(r.data);
      else setError(r.message);
    });
  }, [month]);

  async function regenerate() {
    setBusy(true);
    const r = await api<Report>(`/reports/${month}?refresh=true`);
    setBusy(false);
    if (r.ok) setReport(r.data);
    else setError(r.message);
  }

  if (error && !list) return <Alert kind="error">{error}</Alert>;
  if (!list) return <p className="text-muted-foreground py-10 text-center text-sm">Loading reports…</p>;

  if (list.months.length === 0)
    return (
      <>
        <PageHeader title="Monthly Reports" description="A clear review of each month: where the money went, what changed and what to try next." />
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <FileTextIcon className="text-muted-foreground size-10" />
            <p className="font-medium">No reports yet</p>
            <p className="text-muted-foreground max-w-md text-sm">
              Reports appear for every month that has transactions. <Link href="/import" className="underline">Import a statement</Link> to get your first one.
            </p>
          </CardContent>
        </Card>
      </>
    );

  const c = report?.currency ?? "INR";
  return (
    <>
      <PageHeader
        title="Monthly Reports"
        description="A clear review of each month: where the money went, what changed and what to try next."
        action={
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <NativeSelect aria-label="Month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-44">
              {list.months.map((m) => <option key={m.month} value={m.month}>{formatMonth(m.month)}</option>)}
            </NativeSelect>
            <Button variant="outline" onClick={regenerate} disabled={busy}><RefreshCwIcon /> Refresh</Button>
            <Button variant="outline" onClick={() => report && downloadCsv(report)} disabled={!report || report.month !== month}><DownloadIcon /> CSV</Button>
            <Button variant="outline" onClick={() => window.print()}><PrinterIcon /> Print / PDF</Button>
          </div>
        }
      />
      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}
      {!report || busy || report.month !== month ? (
        <p className="text-muted-foreground py-10 text-center text-sm">Preparing your report…</p>
      ) : (
        <ReportBody r={report} c={c} ai={list.ai} />
      )}
    </>
  );
}

function ReportBody({ r, c, ai }: { r: Report; c: string; ai: string }) {
  const s = r.summary;
  const p = r.previous;
  const delta = (a: string, b: string) => {
    const d = Number(a) - Number(b);
    return Number(b) === 0 ? undefined : `${d >= 0 ? "+" : "−"}${formatMoney(Math.abs(d), c)} vs ${formatMonth(p.month)}`;
  };
  return (
    <div className="space-y-6">
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            {formatMonth(r.month)} in a nutshell
            {r.narrative_source === "ai" ? <Badge variant="secondary"><SparklesIcon /> Written by AI from your numbers</Badge> : <Badge variant="outline">Summary</Badge>}
          </CardTitle>
          <CardDescription>
            Generated {formatDate(r.generated_at.slice(0, 10))}. {ai !== "ready" && r.narrative_source !== "ai" && "AI summaries turn on when an AI key is added."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="leading-relaxed whitespace-pre-line">{r.narrative}</p>
          {r.suggestions.length > 0 && (
            <div>
              <p className="text-sm font-medium">For next month</p>
              <ul className="list-disc pl-5 text-sm">{r.suggestions.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Money in" value={formatMoney(s.income, c)} sub={delta(s.income, p.income)} badge={<BasisBadge basis="actual" />} />
        <Stat label="Money out" value={formatMoney(s.spending, c)} sub={delta(s.spending, p.spending)} />
        <Stat label="Left over" value={formatMoney(s.net, c)} tone={Number(s.net) < 0 ? "bad" : "good"} />
        <Stat label="Saved of income" value={s.savings_rate ? `${s.savings_rate}%` : "—"} sub={p.savings_rate ? `${p.savings_rate}% last month` : undefined} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Highlights</CardTitle></CardHeader>
          <CardContent><ul className="list-disc space-y-1 pl-5 text-sm">{r.highlights.map((h) => <li key={h}>{h}</li>)}</ul></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Where the money went</CardTitle><CardDescription>Compared with {formatMonth(p.month)}</CardDescription></CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {r.categories.filter((x) => Number(x.amount) > 0).slice(0, 8).map((x) => (
                <li key={x.category} className="flex items-center justify-between gap-2 py-1.5">
                  <span>{x.category} <span className="text-muted-foreground text-xs">{x.share_percent ? `${Number(x.share_percent).toFixed(0)}%` : ""}</span></span>
                  <span className="tabular-nums">
                    {formatMoney(x.amount, c)}{" "}
                    {x.change_percent && Number(x.change) !== 0 && <span className={`text-xs ${Number(x.change) > 0 ? "text-destructive" : "text-success"}`}>{Number(x.change) > 0 ? "▲" : "▼"}{Math.abs(Number(x.change_percent)).toFixed(0)}%</span>}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        {r.budgets.items.length > 0 && (
          <Card>
            <CardHeader><CardTitle>Budgets</CardTitle><CardDescription>{formatMoney(r.budgets.total_spent, c)} of {formatMoney(r.budgets.total_budget, c)}</CardDescription></CardHeader>
            <CardContent>
              <ul className="divide-y text-sm">
                {r.budgets.items.map((b) => (
                  <li key={b.id} className="flex justify-between py-1.5">
                    <span>{b.category_name}</span>
                    <span className={`tabular-nums ${b.state === "over" ? "text-destructive" : ""}`}>{formatMoney(b.spent, c)} / {formatMoney(b.amount, c)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader><CardTitle>Goals and subscriptions</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {r.goals.length === 0 ? <p className="text-muted-foreground">No goals yet.</p> : (
              <ul className="divide-y">
                {r.goals.map((g) => (
                  <li key={g.name} className="flex justify-between py-1.5">
                    <span>{g.name}</span>
                    <span className="tabular-nums">{Number(g.progress_percent).toFixed(0)}%{Number(g.added_this_month) > 0 && ` · +${formatMoney(g.added_this_month, c)}`}</span>
                  </li>
                ))}
              </ul>
            )}
            <p>Regular payments: {formatMoney(r.subscriptions.monthly_total, c)} a month across {r.subscriptions.count}.</p>
          </CardContent>
        </Card>
      </div>

      {r.largest_expenses.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Largest expenses</CardTitle></CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {r.largest_expenses.map((t, i) => (
                <li key={i} className="flex justify-between gap-3 py-1.5">
                  <span className="min-w-0 truncate">{formatDate(t.date)} · {t.description}</span>
                  <span className="shrink-0 tabular-nums">{formatMoney(t.amount, c)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
