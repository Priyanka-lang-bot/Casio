"use client";

import { useEffect, useState } from "react";
import { PencilIcon, PiggyBankIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
import { NudgeList } from "@/components/nudge-list";
import { PageHeader } from "@/components/page-header";
import { Progress, Stat } from "@/components/stat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import type { BudgetItem, BudgetPage } from "@/lib/planning-types";
import type { Category } from "@/lib/types";

const STATE = {
  over: { label: "Over budget", variant: "destructive" },
  near: { label: "Almost used", variant: "warning" },
  on_pace_to_exceed: { label: "Running ahead", variant: "warning" },
  ok: { label: "On track", variant: "success" },
} as const;

type Editing = { id?: string; category_id: string; amount: string } | null;

export function BudgetsView() {
  const [month, setMonth] = useState("");
  const [data, setData] = useState<BudgetPage | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<BudgetItem | null>(null);
  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  useEffect(() => {
    api<Category[]>("/categories").then((r) => r.ok && setCats(r.data.filter((c) => c.kind === "expense")));
  }, []);
  useEffect(() => {
    api<BudgetPage>(`/budgets${month ? `?month=${month}` : ""}`).then((r) => (r.ok ? setData(r.data) : setError(r.message)));
  }, [month, version]);

  async function addSuggested(category_id: string, amount: string) {
    const r = await api("/budgets", { category_id, amount });
    if (!r.ok) return setError(r.message);
    reload();
  }

  if (error && !data) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-muted-foreground py-10 text-center text-sm">Loading budgets…</p>;
  const c = data.currency;
  const used = new Set(data.items.map((i) => i.category_id));

  return (
    <>
      <PageHeader
        title="Budgets"
        description="Set a monthly limit for the categories you want to keep an eye on. Spending is counted from your transactions."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="Month" type="month" className="w-full sm:w-44" value={month || data.month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
            <Button onClick={() => setEditing({ category_id: "", amount: "" })}>
              <PlusIcon /> Add budget
            </Button>
          </div>
        }
      />
      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total budget" value={formatMoney(data.total_budget, c)} sub={`${data.items.length} categor${data.items.length === 1 ? "y" : "ies"}`} />
        <Stat label="Spent so far" value={formatMoney(data.total_spent, c)} badge={<BasisBadge basis="actual" />} sub={formatMonth(data.month)} />
        <Stat label="Left to spend" value={formatMoney(data.total_remaining, c)} tone={Number(data.total_remaining) < 0 ? "bad" : undefined} />
        <Stat
          label="Month progress"
          value={`${Math.round((data.days_elapsed / data.days_in_month) * 100)}%`}
          sub={data.is_current_month ? `Day ${data.days_elapsed} of ${data.days_in_month}` : "Month finished"}
        />
      </div>

      {data.is_current_month && (
        <div className="mb-6">
          <NudgeList limit={4} filter={(n) => n.kind.startsWith("budget") || n.kind === "spending_spike"} />
        </div>
      )}

      {data.items.length === 0 ? (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <PiggyBankIcon className="text-muted-foreground size-10" />
            <p className="font-medium">No budgets yet</p>
            <p className="text-muted-foreground max-w-md text-sm">
              Pick a category like Food and Dining and decide how much you want to spend on it each month. CASIO will warn you before you go over.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Your budgets for {formatMonth(data.month)}</CardTitle>
            {data.is_current_month && (
              <CardDescription>“By month end” is a forecast at your current pace, not a certainty.</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {data.items.map((b) => {
                const pct = Number(b.percent_used);
                const s = STATE[b.state];
                return (
                  <li key={b.id} className="space-y-2 py-4 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{b.category_name}</span>
                        <Badge variant={s.variant}>{s.label}</Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-sm tabular-nums">
                          {formatMoney(b.spent, c)} <span className="text-muted-foreground">of {formatMoney(b.amount, c)}</span>
                        </span>
                        <Button variant="ghost" size="icon" className="size-8" aria-label={`Edit ${b.category_name} budget`} onClick={() => setEditing({ id: b.id, category_id: b.category_id, amount: b.amount })}>
                          <PencilIcon className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8" aria-label={`Delete ${b.category_name} budget`} onClick={() => setDeleting(b)}>
                          <Trash2Icon className="size-4" />
                        </Button>
                      </div>
                    </div>
                    <Progress value={pct} tone={b.state === "over" ? "bad" : b.state === "ok" ? "good" : "warn"} />
                    <p className="text-muted-foreground text-xs">
                      {Number(b.remaining) >= 0 ? `${formatMoney(b.remaining, c)} left` : `${formatMoney(-Number(b.remaining), c)} over`} · {pct.toFixed(0)}% used
                      {data.is_current_month && ` · about ${formatMoney(b.projected, c)} by month end`}
                      {b.usual_spend && ` · you usually spend ${formatMoney(b.usual_spend, c)}`}
                    </p>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {data.suggestions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Suggested budgets</CardTitle>
              <CardDescription>Based on what you usually spend (average of your last few months).</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="divide-y">
                {data.suggestions.map((s) => (
                  <li key={s.category_id} className="flex items-center justify-between gap-3 py-2">
                    <div>
                      <p className="text-sm font-medium">{s.category_name}</p>
                      <p className="text-muted-foreground text-xs">Usually {formatMoney(s.usual_spend, c)} a month</p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => addSuggested(s.category_id, s.suggested_amount)}>
                      Add {formatMoney(s.suggested_amount, c)}
                    </Button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
        {data.unbudgeted.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Spending without a budget</CardTitle>
              <CardDescription>{formatMonth(data.month)}, from your transactions.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="divide-y text-sm">
                {data.unbudgeted.map((u) => (
                  <li key={u.category_name} className="flex justify-between py-2">
                    <span>{u.category_name}</span>
                    <span className="tabular-nums">{formatMoney(u.spent, c)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>

      {editing && <BudgetDialog
        key={editing.id ?? "new"}
        editing={editing}
        categories={cats.filter((x) => !used.has(x.id) || x.id === editing?.category_id)}
        currency={c}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          reload();
        }}
      />}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete this budget?"
        description={`The ${deleting?.category_name} budget will be removed. Your transactions are not affected.`}
        confirmLabel="Delete budget"
        onConfirm={async () => {
          if (deleting) await api(`/budgets/${deleting.id}`, undefined, "DELETE");
          reload();
        }}
      />
    </>
  );
}

function BudgetDialog({ editing, categories, currency, onClose, onSaved }: {
  editing: NonNullable<Editing>; categories: Category[]; currency: string; onClose: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState({ category_id: editing.category_id, amount: editing.amount });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editing.id ? "Edit budget" : "Add a budget"}</DialogTitle>
          <DialogDescription>How much do you want to spend on this each month?</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!form.category_id) return setError("Please choose a category.");
            if (!(Number(form.amount) > 0)) return setError("Enter an amount above zero.");
            setBusy(true);
            const r = editing.id
              ? await api(`/budgets/${editing.id}`, { amount: form.amount }, "PATCH")
              : await api("/budgets", form);
            setBusy(false);
            if (!r.ok) return setError(r.fields.amount ?? r.message);
            onSaved();
          }}
        >
          {error && <Alert kind="error">{error}</Alert>}
          <div className="space-y-1.5">
            <Label htmlFor="b-cat">Category</Label>
            <NativeSelect id="b-cat" value={form.category_id} disabled={!!editing.id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
              <option value="">Choose…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-amt">Monthly limit ({currency})</Label>
            <Input id="b-amt" inputMode="decimal" type="number" min="1" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save budget"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
