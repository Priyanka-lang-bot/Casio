"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { HistoryIcon, PencilIcon, Trash2Icon, TriangleAlertIcon, WandSparklesIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Category, Correction, Priority, Rule, RuleSave } from "@/lib/types";

const PRIORITY_LABEL: Record<Priority, string> = { high: "High priority", normal: "Normal priority", low: "Low priority" };

export function RulesView() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Rule | null>(null);
  const [removing, setRemoving] = useState<Rule | null>(null);

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);

  useEffect(() => {
    api<Rule[]>("/rules").then((r) => (r.ok ? setRules(r.data) : setError(r.message)));
    api<Correction[]>("/rules/corrections?limit=10").then((c) => c.ok && setCorrections(c.data));
  }, [version]);
  useEffect(() => {
    api<Category[]>("/categories").then((r) => r.ok && setCategories(r.data));
  }, []);

  async function update(rule: Rule, body: Partial<Pick<Rule, "active" | "priority" | "category_id" | "match_type" | "pattern">>) {
    setError("");
    const r = await api<RuleSave>(`/rules/${rule.id}`, body, "PATCH");
    if (!r.ok) {
      setError(r.message);
      return false;
    }
    const n = r.data.changed_transactions;
    setNotice(n ? `Done. ${n} transaction${n === 1 ? "" : "s"} updated to match.` : "Saved.");
    load();
    return true;
  }

  return (
    <>
      <PageHeader
        title="Learned Rules"
        description="When you fix a category and choose “Always”, CASIO remembers it here. Rules run before CASIO's own guesses and before AI, and never change a category you picked yourself."
      />
      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}
      {notice && <div className="mb-4"><Alert kind="success">{notice}</Alert></div>}

      {rules === null ? (
        <p className="text-muted-foreground py-10 text-center text-sm">Loading…</p>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <WandSparklesIcon className="text-muted-foreground size-10" />
            <p className="font-medium">No rules yet</p>
            <p className="text-muted-foreground max-w-md text-sm">
              Change a transaction&apos;s category on the <Link href="/transactions" className="underline">Transactions</Link> page or
              while checking an import. CASIO will ask whether to remember it for similar payments.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="py-0">
          <ul className="divide-y">
            {rules.map((r) => (
              <li key={r.id} className={`px-4 py-4 ${r.active ? "" : "bg-muted/40"}`}>
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {r.match_type === "merchant" ? "Shop name starts with" : "Description contains"}{" "}
                      <code className="bg-muted rounded px-1.5 py-0.5 text-sm">{r.pattern}</code>{" "}
                      <span className="text-muted-foreground">→</span> {r.category_name}
                    </p>
                    <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                      <span>{r.applies_to === "income" ? "Money in" : "Money out"}</span>
                      <span aria-hidden>·</span>
                      <span>{PRIORITY_LABEL[r.priority]}</span>
                      <span aria-hidden>·</span>
                      <Link href={`/transactions?rule_id=${r.id}`} className="hover:underline">
                        Used on {r.times_applied} transaction{r.times_applied === 1 ? "" : "s"}
                      </Link>
                      {r.times_overridden > 0 && (
                        <>
                          <span aria-hidden>·</span>
                          <span>you changed {r.times_overridden} of them back</span>
                        </>
                      )}
                      <span aria-hidden>·</span>
                      <Badge variant={r.weak ? "warning" : "success"} title="How often you kept what this rule chose">
                        {Math.round(r.confidence * 100)}% reliable
                      </Badge>
                      {!r.active && <Badge variant="outline">Paused</Badge>}
                    </div>
                    {r.weak && (
                      <p className="text-warning mt-2 flex gap-1.5 text-xs">
                        <TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
                        You often change what this rule picks. Edit it to be more specific, or remove it.
                      </p>
                    )}
                    {r.conflicts.map((c) => (
                      <p key={c.rule_id} className="text-warning mt-2 flex gap-1.5 text-xs">
                        <TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
                        <span>
                          Overlaps with “{c.pattern}” → {c.category_name} on {c.transactions} transaction{c.transactions === 1 ? "" : "s"}.{" "}
                          {c.this_wins ? "This rule wins there." : "That rule wins there (higher priority or more specific)."}
                        </span>
                      </p>
                    ))}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <label className="mr-2 flex items-center gap-1.5 text-xs">
                      <Checkbox checked={r.active} onCheckedChange={(v) => update(r, { active: v === true })} aria-label={`Use rule ${r.pattern}`} />
                      On
                    </label>
                    <Button variant="ghost" size="icon" aria-label={`Edit rule ${r.pattern}`} onClick={() => setEditing(r)}>
                      <PencilIcon />
                    </Button>
                    <Button variant="ghost" size="icon" aria-label={`Remove rule ${r.pattern}`} onClick={() => setRemoving(r)}>
                      <Trash2Icon />
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><HistoryIcon className="size-4" /> Your recent corrections</CardTitle>
          <CardDescription>Every category you changed. CASIO uses these to suggest rules, but only makes one when you say so.</CardDescription>
        </CardHeader>
        <CardContent>
          {corrections.length === 0 ? (
            <p className="text-muted-foreground text-sm">None yet.</p>
          ) : (
            <ul className="divide-y text-sm">
              {corrections.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
                  <span className="min-w-0 flex-1 truncate">{c.description}</span>
                  <span className="text-muted-foreground text-xs">
                    {c.from_category ?? "No category"} → <span className="text-foreground">{c.to_category ?? "No category"}</span> · {formatDate(c.created_at.slice(0, 10))}
                  </span>
                  {c.made_rule && <Badge variant="success">Made a rule</Badge>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <EditRuleDialog rule={editing} categories={categories} onClose={() => setEditing(null)} onSave={update} />
      <RemoveRuleDialog
        rule={removing}
        onClose={() => setRemoving(null)}
        onRemoved={(n) => {
          setRemoving(null);
          setNotice(`Rule removed. ${n} transaction${n === 1 ? "" : "s"} went back to the category ${n === 1 ? "it" : "they"} had before.`);
          load();
        }}
      />
    </>
  );
}

function EditRuleDialog({
  rule,
  categories,
  onClose,
  onSave,
}: {
  rule: Rule | null;
  categories: Category[];
  onClose: () => void;
  onSave: (rule: Rule, body: Partial<Rule>) => Promise<boolean>;
}) {
  return (
    <Dialog open={rule !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit rule</DialogTitle>
          <DialogDescription>Changes apply straight away to transactions this rule chose.</DialogDescription>
        </DialogHeader>
        {rule && <EditRuleForm key={rule.id} rule={rule} categories={categories} onClose={onClose} onSave={onSave} />}
      </DialogContent>
    </Dialog>
  );
}

function EditRuleForm({ rule, categories, onClose, onSave }: { rule: Rule; categories: Category[]; onClose: () => void; onSave: (rule: Rule, body: Partial<Rule>) => Promise<boolean> }) {
  const [matchType, setMatchType] = useState(rule.match_type);
  const [pattern, setPattern] = useState(rule.pattern);
  const [categoryId, setCategoryId] = useState(rule.category_id);
  const [priority, setPriority] = useState(rule.priority);
  const [busy, setBusy] = useState(false);
  const fitting = categories.filter((c) => c.kind === "transfer" || c.kind === rule.applies_to);
  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        const ok = await onSave(rule, { match_type: matchType, pattern, category_id: categoryId, priority });
        setBusy(false);
        if (ok) onClose();
      }}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="rule-match">Match</Label>
          <NativeSelect id="rule-match" value={matchType} onChange={(e) => setMatchType(e.target.value as Rule["match_type"])}>
            <option value="merchant">Shop name starts with</option>
            <option value="contains">Description contains</option>
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rule-pattern">Words</Label>
          <Input id="rule-pattern" value={pattern} onChange={(e) => setPattern(e.target.value)} maxLength={100} required />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="rule-cat">Category</Label>
        <NativeSelect id="rule-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          {fitting.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </NativeSelect>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="rule-priority">Priority when rules disagree</Label>
        <NativeSelect id="rule-priority" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
          <option value="high">High: wins over other rules</option>
          <option value="normal">Normal: the more specific rule wins</option>
          <option value="low">Low: only if no other rule matches</option>
        </NativeSelect>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save rule"}</Button>
      </DialogFooter>
    </form>
  );
}

function RemoveRuleDialog({ rule, onClose, onRemoved }: { rule: Rule | null; onClose: () => void; onRemoved: (reverted: number) => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={rule !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Remove this rule?</DialogTitle>
          <DialogDescription>
            {rule &&
              `The ${rule.currently_applied} transaction${rule.currently_applied === 1 ? "" : "s"} it categorised will go back to the category they had before. Future imports won't use it.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Keep it</Button>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={async () => {
              if (!rule) return;
              setBusy(true);
              const r = await api<{ reverted_transactions: number }>(`/rules/${rule.id}`, undefined, "DELETE");
              setBusy(false);
              if (r.ok) onRemoved(r.data.reverted_transactions);
            }}
          >
            Remove rule
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
