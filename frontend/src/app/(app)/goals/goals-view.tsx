"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PencilIcon, PlusIcon, TargetIcon, Trash2Icon } from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
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
import { formatDate, formatMoney } from "@/lib/format";
import type { Goal, GoalPage } from "@/lib/planning-types";

export const GOAL_KINDS: Record<string, string> = {
  emergency_fund: "Emergency fund",
  purchase: "Big purchase",
  education: "Education",
  travel: "Travel",
  home: "Home",
  debt: "Pay off debt",
  other: "Other",
};

const STATE: Record<Goal["state"], { label: string; variant: "success" | "warning" | "destructive" | "secondary" | "outline" }> = {
  achieved: { label: "Achieved 🎉", variant: "success" },
  on_track: { label: "On track", variant: "success" },
  behind: { label: "Behind", variant: "warning" },
  past_due: { label: "Past target date", variant: "destructive" },
  no_plan: { label: "Needs a monthly amount", variant: "secondary" },
  no_date: { label: "No target date", variant: "outline" },
  paused: { label: "Paused", variant: "secondary" },
};

type Form = { name: string; kind: string; target_amount: string; saved_amount: string; target_date: string; monthly_contribution: string; priority: string; status: string };
const EMPTY: Form = { name: "", kind: "other", target_amount: "", saved_amount: "0", target_date: "", monthly_contribution: "", priority: "2", status: "active" };

export function GoalsView() {
  const [data, setData] = useState<GoalPage | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<{ id?: string; form: Form } | null>(null);
  const [adding, setAdding] = useState<Goal | null>(null);
  const [deleting, setDeleting] = useState<Goal | null>(null);
  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  useEffect(() => {
    api<GoalPage>("/goals").then((r) => (r.ok ? setData(r.data) : setError(r.message)));
  }, [version]);

  if (error && !data) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-muted-foreground py-10 text-center text-sm">Loading goals…</p>;
  const c = data.currency;
  const t = data.totals;
  const surplus = Number(t.monthly_surplus);
  const contrib = Number(t.monthly_contributions);
  const hasEF = data.goals.some((g) => g.kind === "emergency_fund");

  return (
    <>
      <PageHeader
        title="Goals"
        description="Save towards the things that matter. CASIO shows your progress and when you'll get there at your current pace."
        action={<Button onClick={() => setEditing({ form: EMPTY })}><PlusIcon /> New goal</Button>}
      />
      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Saved towards goals" value={formatMoney(t.saved, c)} sub={`of ${formatMoney(t.target, c)}`} />
        <Stat label="Planned each month" value={formatMoney(t.monthly_contributions, c)} sub="your goal contributions" />
        <Stat
          label="Usually left over"
          value={formatMoney(t.monthly_surplus, c)}
          badge={<BasisBadge basis={t.plan_basis === "actual" ? "actual" : "estimate"} />}
          tone={surplus < 0 ? "bad" : undefined}
        />
        <Stat
          label="Room after goals"
          value={formatMoney(surplus - contrib, c)}
          tone={surplus - contrib < 0 ? "bad" : "good"}
          sub={surplus - contrib < 0 ? "Your goals need more than you have left" : "Spare each month"}
        />
      </div>

      {surplus - contrib < 0 && contrib > 0 && (
        <div className="mb-6">
          <Alert kind="info">
            Your goals need {formatMoney(contrib, c)} a month but you usually have {formatMoney(surplus, c)} left. Try the{" "}
            <Link href="/what-if" className="underline">What-If Simulator</Link> to see what would make them fit.
          </Alert>
        </div>
      )}

      {!hasEF && data.suggested_emergency_fund && (
        <Card className="border-primary/30 bg-primary/5 mb-6">
          <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium">Start with an emergency fund</p>
              <p className="text-muted-foreground text-sm">
                Three months of your usual spending is about {formatMoney(data.suggested_emergency_fund, c)}. It protects your other goals when something unexpected happens.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => setEditing({ form: { ...EMPTY, name: "Emergency fund", kind: "emergency_fund", target_amount: String(Math.round(Number(data.suggested_emergency_fund))), priority: "1" } })}
            >
              Create it
            </Button>
          </CardContent>
        </Card>
      )}

      {data.goals.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <TargetIcon className="text-muted-foreground size-10" />
            <p className="font-medium">No goals yet</p>
            <p className="text-muted-foreground max-w-md text-sm">Add a goal like a new laptop, a trip or a home deposit. Give it a target date and a monthly amount, and CASIO will tell you if you&apos;re on track.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.goals.map((g) => {
            const s = STATE[g.state];
            return (
              <Card key={g.id} className={g.status !== "active" ? "opacity-80" : undefined}>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    {g.name} <Badge variant={s.variant}>{s.label}</Badge>
                  </CardTitle>
                  <CardDescription>
                    {GOAL_KINDS[g.kind] ?? g.kind}
                    {g.target_date && ` · by ${formatDate(g.target_date)}`}
                    {g.priority === 1 && " · high priority"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xl font-semibold tabular-nums">{formatMoney(g.saved_amount, c)}</span>
                    <span className="text-muted-foreground text-sm">of {formatMoney(g.target_amount, c)} · {Number(g.progress_percent).toFixed(0)}%</span>
                  </div>
                  <Progress value={Number(g.progress_percent)} tone={g.state === "achieved" ? "good" : g.state === "behind" || g.state === "past_due" ? "warn" : undefined} />
                  <ul className="text-muted-foreground space-y-1 text-sm">
                    {g.monthly_contribution && Number(g.monthly_contribution) > 0 && <li>Putting aside {formatMoney(g.monthly_contribution, c)} a month</li>}
                    {g.projected_finish && g.state !== "achieved" && (
                      <li className="flex items-center gap-2">At this pace: {formatDate(g.projected_finish)} <BasisBadge basis="forecast" /></li>
                    )}
                    {g.needed_per_month && g.state !== "achieved" && <li>Needed to hit the date: {formatMoney(g.needed_per_month, c)} a month</li>}
                  </ul>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button size="sm" onClick={() => setAdding(g)}>Add money</Button>
                    <Button size="sm" variant="outline" onClick={() => setEditing({ id: g.id, form: toForm(g) })}><PencilIcon /> Edit</Button>
                    <Button size="sm" variant="ghost" aria-label={`Delete ${g.name}`} onClick={() => setDeleting(g)}><Trash2Icon /></Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {editing && <GoalDialog key={editing.id ?? "new"} editing={editing} currency={c} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
      {adding && <ContributionDialog key={adding.id} goal={adding} currency={c} onClose={() => setAdding(null)} onSaved={() => { setAdding(null); reload(); }} />}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete this goal?"
        description={`“${deleting?.name}” and its history will be removed. This can't be undone.`}
        confirmLabel="Delete goal"
        onConfirm={async () => {
          if (deleting) await api(`/goals/${deleting.id}`, undefined, "DELETE");
          reload();
        }}
      />
    </>
  );
}

function toForm(g: Goal): Form {
  return {
    name: g.name, kind: g.kind, target_amount: g.target_amount, saved_amount: g.saved_amount, target_date: g.target_date ?? "",
    monthly_contribution: g.monthly_contribution ?? "", priority: String(g.priority), status: g.status,
  };
}

function GoalDialog({ editing, currency, onClose, onSaved }: { editing: { id?: string; form: Form }; currency: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState<Form>(editing.form);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing?.id ? "Edit goal" : "New goal"}</DialogTitle>
          <DialogDescription>Amounts in {currency}. The date and monthly amount are optional, but they let CASIO tell you if you&apos;re on track.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            const body = {
              name: f.name, kind: f.kind, target_amount: f.target_amount, saved_amount: f.saved_amount || "0",
              target_date: f.target_date || null, monthly_contribution: f.monthly_contribution || null, priority: Number(f.priority),
              ...(editing?.id ? { status: f.status } : {}),
            };
            const r = editing?.id ? await api(`/goals/${editing.id}`, body, "PUT") : await api("/goals", body);
            setBusy(false);
            if (!r.ok) {
              setErrors(r.fields);
              return setError(r.message);
            }
            onSaved();
          }}
        >
          {error && <Alert kind="error">{error}</Alert>}
          <Field label="Goal name" error={errors.name}><Input value={f.name} onChange={set("name")} placeholder="e.g. New laptop" required /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Type" error={errors.kind}>
              <NativeSelect value={f.kind} onChange={set("kind")}>
                {Object.entries(GOAL_KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Priority">
              <NativeSelect value={f.priority} onChange={set("priority")}>
                <option value="1">High</option><option value="2">Normal</option><option value="3">Low</option>
              </NativeSelect>
            </Field>
            <Field label="Target amount" error={errors.target_amount}><Input type="number" min="1" step="0.01" inputMode="decimal" value={f.target_amount} onChange={set("target_amount")} required /></Field>
            <Field label="Already saved" error={errors.saved_amount}><Input type="number" min="0" step="0.01" inputMode="decimal" value={f.saved_amount} onChange={set("saved_amount")} /></Field>
            <Field label="Target date (optional)" error={errors.target_date}><Input type="date" value={f.target_date} onChange={set("target_date")} /></Field>
            <Field label="Monthly amount (optional)" error={errors.monthly_contribution}><Input type="number" min="0" step="0.01" inputMode="decimal" value={f.monthly_contribution} onChange={set("monthly_contribution")} /></Field>
            {editing?.id && (
              <Field label="Status">
                <NativeSelect value={f.status} onChange={set("status")}>
                  <option value="active">Active</option><option value="paused">Paused</option><option value="achieved">Achieved</option>
                </NativeSelect>
              </Field>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save goal"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ContributionDialog({ goal, currency, onClose, onSaved }: { goal: Goal; currency: string; onClose: () => void; onSaved: () => void }) {
  const [amount, setAmount] = useState(goal.monthly_contribution ?? "");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add money to “{goal?.name}”</DialogTitle>
          <DialogDescription>Record money you&apos;ve set aside. Use a minus sign (e.g. -500) if you took some out.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!goal) return;
            setBusy(true);
            const r = await api(`/goals/${goal.id}/contributions`, { amount, note: note || null });
            setBusy(false);
            if (!r.ok) return setError(r.fields.amount ?? r.message);
            onSaved();
          }}
        >
          {error && <Alert kind="error">{error}</Alert>}
          <Field label={`Amount (${currency})`}><Input type="number" step="0.01" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></Field>
          <Field label="Note (optional)"><Input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder="e.g. November savings" /></Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Add"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <Label asChild><span>{label}</span></Label>
      {children}
      {error && <span className="text-destructive block text-sm">{error}</span>}
    </label>
  );
}
