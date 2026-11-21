"use client";

import { useEffect, useState } from "react";
import { FlaskConicalIcon, PlusIcon, SparklesIcon, Trash2Icon } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatDate, formatMoney, formatMonth } from "@/lib/format";
import type { Change, SimResult } from "@/lib/planning-types";
import type { Category } from "@/lib/types";

const EXAMPLES = [
  "What if I reduce dining expenses by 30%?",
  "What if my rent increases by ₹3,000?",
  "What if my income decreases by 10%?",
  "What if I save another ₹2,000 every month?",
];

const TYPES: { value: Change["type"]; label: string }[] = [
  { value: "category_change", label: "Change spending in a category" },
  { value: "income_change", label: "Change my income" },
  { value: "new_expense", label: "Add a new monthly cost" },
  { value: "extra_saving", label: "Save extra each month" },
  { value: "one_time_expense", label: "A one-off expense" },
];

type Draft = { type: Change["type"]; category: string; label: string; mode: "percent" | "amount"; value: string; direction: "down" | "up" };
const NEW: Draft = { type: "category_change", category: "Food and Dining", label: "", mode: "percent", value: "", direction: "down" };

function toChange(d: Draft): Change | null {
  const v = Number(d.value);
  if (!(v > 0)) return null;
  const signed = d.direction === "down" ? -v : v;
  if (d.type === "category_change") return { type: d.type, category: d.category, ...(d.mode === "percent" ? { percent: signed } : { amount: signed }) };
  if (d.type === "income_change") return { type: d.type, ...(d.mode === "percent" ? { percent: signed } : { amount: signed }) };
  return { type: d.type, amount: v, label: d.label || undefined };
}

export function WhatIfView({ initialQuestion }: { initialQuestion?: string }) {
  const [question, setQuestion] = useState(initialQuestion ?? "");
  const [drafts, setDrafts] = useState<Draft[]>([{ ...NEW }]);
  const [cats, setCats] = useState<string[]>([]);
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Opened with a question (from a link, or the demo's ready-made scenario): run it straight away.
  useEffect(() => {
    if (initialQuestion) void ask(initialQuestion);
  }, [initialQuestion]);

  useEffect(() => {
    api<Category[]>("/categories").then((r) => r.ok && setCats(r.data.filter((c) => c.kind === "expense").map((c) => c.name)));
  }, []);

  async function ask(q: string) {
    setQuestion(q);
    setBusy(true);
    setError("");
    const r = await api<SimResult>("/what-if/ask", { question: q });
    setBusy(false);
    if (!r.ok) return setError(r.message);
    setResult(r.data);
  }

  async function runBuilt() {
    const changes = drafts.map(toChange).filter((x): x is Change => !!x);
    if (!changes.length) return setError("Enter an amount for at least one change.");
    setBusy(true);
    setError("");
    const r = await api<SimResult>("/what-if", { changes });
    setBusy(false);
    if (!r.ok) return setError(r.message);
    setResult(r.data);
  }

  const upd = (i: number, patch: Partial<Draft>) => setDrafts((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  return (
    <>
      <PageHeader
        title="What-If Simulator"
        description="Try a change before you make it. CASIO starts from your usual month, applies the change and shows the effect on your savings and goals."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><SparklesIcon className="size-4" /> Ask in your own words</CardTitle>
            <CardDescription>CASIO turns your question into a scenario. All the maths is done by CASIO&apos;s calculator, not guessed.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); if (question.trim()) ask(question.trim()); }}>
              <Input aria-label="Your what-if question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What if I cut shopping by ₹2,000?" maxLength={500} />
              <Button type="submit" disabled={busy || question.trim().length < 3}>{busy ? "Working…" : "Simulate"}</Button>
            </form>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" onClick={() => ask(ex)} className="bg-muted hover:bg-accent rounded-full px-3 py-1 text-left text-xs">
                  {ex}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><FlaskConicalIcon className="size-4" /> Or build it step by step</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {drafts.map((d, i) => (
              <div key={i} className="space-y-2 rounded-lg border p-3">
                <div className="flex gap-2">
                  <NativeSelect aria-label="Kind of change" value={d.type} onChange={(e) => upd(i, { type: e.target.value as Change["type"] })}>
                    {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </NativeSelect>
                  {drafts.length > 1 && (
                    <Button variant="ghost" size="icon" aria-label="Remove this change" onClick={() => setDrafts((ds) => ds.filter((_, j) => j !== i))}><Trash2Icon /></Button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {d.type === "category_change" && (
                    <div className="col-span-2">
                      <Label className="sr-only" htmlFor={`cat-${i}`}>Category</Label>
                      <NativeSelect id={`cat-${i}`} value={d.category} onChange={(e) => upd(i, { category: e.target.value })}>
                        {cats.map((c) => <option key={c}>{c}</option>)}
                      </NativeSelect>
                    </div>
                  )}
                  {(d.type === "category_change" || d.type === "income_change") && (
                    <>
                      <NativeSelect aria-label="Up or down" value={d.direction} onChange={(e) => upd(i, { direction: e.target.value as Draft["direction"] })}>
                        <option value="down">Down by</option><option value="up">Up by</option>
                      </NativeSelect>
                      <NativeSelect aria-label="Percent or amount" value={d.mode} onChange={(e) => upd(i, { mode: e.target.value as Draft["mode"] })}>
                        <option value="percent">%</option><option value="amount">Amount</option>
                      </NativeSelect>
                    </>
                  )}
                  {(d.type === "new_expense" || d.type === "one_time_expense") && (
                    <Input className="col-span-2" aria-label="What is it?" placeholder="What is it? (optional)" value={d.label} maxLength={60} onChange={(e) => upd(i, { label: e.target.value })} />
                  )}
                  <Input className="col-span-2 sm:col-span-2" aria-label="Value" type="number" min="0" step="any" inputMode="decimal" placeholder={d.mode === "percent" && (d.type === "category_change" || d.type === "income_change") ? "e.g. 30" : "e.g. 3000"} value={d.value} onChange={(e) => upd(i, { value: e.target.value })} />
                </div>
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setDrafts((ds) => [...ds, { ...NEW }])} disabled={drafts.length >= 5}><PlusIcon /> Add another change</Button>
              <Button size="sm" onClick={runBuilt} disabled={busy}>Run scenario</Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {error && <div className="mt-6"><Alert kind="error">{error}</Alert></div>}
      {result && <ResultView r={result} />}
    </>
  );
}

function ResultView({ r }: { r: SimResult }) {
  const c = r.currency;
  if (!r.has_data)
    return <div className="mt-6"><Alert kind="info">CASIO needs a starting point. Import a statement or fill in your Financial Profile first.</Alert></div>;
  const diff = Number(r.difference.surplus);
  const chart = r.projection.map((p) => ({ month: formatMonth(p.month), "As things are": Number(p.baseline), "With the change": Number(p.scenario) }));
  return (
    <div className="mt-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            Result <BasisBadge basis="forecast" />
            {r.parsed_by && <Badge variant="secondary">Understood by {r.parsed_by === "ai" ? "AI" : "CASIO's rules"}</Badge>}
          </CardTitle>
          <CardDescription>
            {r.changes.map((ch) => `${ch.label}: ${formatMoney(ch.before, c)} → ${formatMoney(ch.after, c)}`).join(" · ")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {r.problems.length > 0 && <Alert kind="info">{r.problems.join(" ")}</Alert>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Compare label="Income per month" a={r.baseline.income} b={r.scenario.income} c={c} />
            <Compare label="Spending per month" a={r.baseline.spending} b={r.scenario.spending} c={c} invert />
            <Compare label="Left over per month" a={r.baseline.surplus} b={r.scenario.surplus} c={c} />
          </div>
          <p className={`text-lg font-semibold ${diff > 0 ? "text-success" : diff < 0 ? "text-destructive" : ""}`}>
            {diff === 0 ? "No change to what's left each month." : `${diff > 0 ? "+" : "−"}${formatMoney(Math.abs(diff), c)} a month · ${Number(r.difference.after_12_months) >= 0 ? "+" : "−"}${formatMoney(Math.abs(Number(r.difference.after_12_months)), c)} after 12 months`}
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {r.explanation.map((e) => <li key={e}>{e}</li>)}
          </ul>
          <p className="text-muted-foreground text-xs">{r.disclaimer}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Savings over the next 12 months</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ left: 8, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" fontSize={12} />
              <YAxis fontSize={12} width={70} tickFormatter={(v) => formatMoney(v, c).replace(/\.00$/, "")} />
              <Tooltip formatter={(v) => formatMoney(Number(v), c)} />
              <Legend />
              <Line isAnimationActive={false} type="monotone" dataKey="As things are" stroke="var(--muted-foreground)" strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} type="monotone" dataKey="With the change" stroke="var(--primary)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {r.goals.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Effect on your goals</CardTitle>
            <CardDescription>Goal contributions shrink if the money left over can&apos;t cover them.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="text-muted-foreground text-left">
                <tr><th className="py-1 font-medium">Goal</th><th className="font-medium">Now: per month → finish</th><th className="font-medium">With change</th><th className="font-medium">Difference</th></tr>
              </thead>
              <tbody>
                {r.goals.map((g) => (
                  <tr key={g.id} className="border-t">
                    <td className="py-2 font-medium">{g.name}</td>
                    <td className="tabular-nums">{formatMoney(g.baseline.monthly, c)} → {g.baseline.finish ? formatDate(g.baseline.finish) : "no date"}</td>
                    <td className="tabular-nums">{formatMoney(g.scenario.monthly, c)} → {g.scenario.finish ? formatDate(g.scenario.finish) : "no date"}</td>
                    <td>{g.months_sooner_or_later ? `${Math.abs(g.months_sooner_or_later)} mo ${g.months_sooner_or_later > 0 ? "later" : "sooner"}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Compare({ label, a, b, c, invert }: { label: string; a: string; b: string; c: string; invert?: boolean }) {
  const d = Number(b) - Number(a);
  const good = invert ? d < 0 : d > 0;
  return (
    <div className="rounded-lg border p-3">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm tabular-nums"><span className="text-muted-foreground">{formatMoney(a, c)}</span> → <span className="font-semibold">{formatMoney(b, c)}</span></p>
      {d !== 0 && <p className={`text-xs ${good ? "text-success" : "text-destructive"}`}>{d > 0 ? "+" : "−"}{formatMoney(Math.abs(d), c)}</p>}
    </div>
  );
}
