"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PencilIcon, PlusIcon, ReceiptIcon, SparklesIcon, Trash2Icon, WandSparklesIcon } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
import { LearnDialog, type LearnResult, type LearnTarget } from "@/components/learn-dialog";
import { PageHeader } from "@/components/page-header";
import { TransactionDialog } from "@/components/transaction-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Category, RuleSave, Transaction } from "@/lib/types";

const PAGE = 50;

export function TransactionsView({ ruleId = "" }: { ruleId?: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<Transaction[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ type: "", category_id: "", month: "", q: "", rule_id: ruleId });
  const [offset, setOffset] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [deleting, setDeleting] = useState<Transaction | null>(null);
  const [learn, setLearn] = useState<LearnTarget | null>(null);
  const [made, setMade] = useState<RuleSave | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
    const res = await api<{ items: Transaction[]; total: number }>(`/transactions?${params}`);
    if (res.ok) {
      setItems(res.data.items);
      setTotal(res.data.total);
      setError("");
    } else setError(res.message);
  }, [filters, offset]);

  useEffect(() => {
    api<Category[]>("/categories").then((r) => r.ok && setCategories(r.data));
  }, []);
  useEffect(() => {
    const t = setTimeout(load, filters.q ? 250 : 0); // wait for typing to pause
    return () => clearTimeout(t);
  }, [load, filters.q]);

  // The user picked a new category: save it, then ask whether to remember it.
  async function changeCategory(t: Transaction, categoryId: string) {
    const body = { type: t.type, amount: t.amount, occurred_on: t.occurred_on, description: t.description, notes: t.notes, category_id: categoryId || null };
    const res = await api<Transaction>(`/transactions/${t.id}`, body, "PUT");
    if (!res.ok) return setError(res.message);
    setItems((list) => list && list.map((x) => (x.id === t.id ? res.data : x)));
    askToLearn(t, res.data);
  }

  function askToLearn(before: Transaction | null, after?: Transaction) {
    if (!before || !after || !after.category_id || before.category_id === after.category_id) return;
    setLearn({ kind: "transaction", id: after.id, description: after.description, categoryId: after.category_id, fromCategory: before.category_name });
  }

  function learned(result: LearnResult) {
    setLearn(null);
    if (result.choice === "rule") {
      setMade(result.saved);
      setNotice("");
      load();
    }
  }

  async function undoRule() {
    if (!made) return;
    const r = await api<{ reverted_transactions: number }>(`/rules/${made.rule.id}`, undefined, "DELETE");
    setMade(null);
    if (r.ok) setNotice(`Rule removed. ${r.data.reverted_transactions} transaction${r.data.reverted_transactions === 1 ? "" : "s"} went back to their earlier category.`);
    load();
  }

  const setFilter = (k: keyof typeof filters, v: string) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v }));
  };
  const filtering = Object.values(filters).some(Boolean);

  return (
    <>
      <PageHeader
        title="Transactions"
        description="Every payment in and out. Add them by hand, or import a bank statement."
        action={
          <Button
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            <PlusIcon /> Add transaction
          </Button>
        }
      />

      <Card className="mb-4 py-4">
        <CardContent className="grid gap-3 px-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="f-q">Search</Label>
            <Input id="f-q" placeholder="Description…" value={filters.q} onChange={(e) => setFilter("q", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-type">Type</Label>
            <NativeSelect id="f-type" value={filters.type} onChange={(e) => setFilter("type", e.target.value)}>
              <option value="">All</option>
              <option value="income">Money in</option>
              <option value="expense">Money out</option>
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-cat">Category</Label>
            <NativeSelect id="f-cat" value={filters.category_id} onChange={(e) => setFilter("category_id", e.target.value)}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-month">Month</Label>
            <Input id="f-month" type="month" value={filters.month} onChange={(e) => setFilter("month", e.target.value)} />
          </div>
        </CardContent>
      </Card>

      {error && <Alert kind="error">{error}</Alert>}
      {filters.rule_id && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <Badge variant="success"><WandSparklesIcon className="size-3" /> Showing transactions one of your rules categorised</Badge>
          <Button size="sm" variant="ghost" onClick={() => setFilter("rule_id", "")}>Show all</Button>
        </div>
      )}
      {made && (
        <div className="bg-success/10 text-success mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-current/20 px-4 py-3 text-sm" role="status">
          <WandSparklesIcon className="size-4 shrink-0" />
          <span className="flex-1">
            {made.replaced ? "Rule updated" : "Rule made"}: {made.rule.match_type === "merchant" ? "shop" : "descriptions with"} “{made.rule.pattern}” → {made.rule.category_name}.{" "}
            {made.changed_transactions > 0
              ? `${made.changed_transactions} earlier transaction${made.changed_transactions === 1 ? " was" : "s were"} updated.`
              : "It will be used from now on."}
          </span>
          <Button size="sm" variant="outline" onClick={undoRule}>Undo</Button>
          <Button size="sm" variant="ghost" asChild><Link href="/rules">See rules</Link></Button>
        </div>
      )}
      {notice && <div className="mb-4"><Alert kind="info">{notice}</Alert></div>}

      {items === null ? (
        <p className="text-muted-foreground py-10 text-center text-sm">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <ReceiptIcon className="text-muted-foreground size-10" />
            {filtering ? (
              <>
                <p className="font-medium">No transactions match these filters.</p>
                <Button variant="outline" onClick={() => setFilters({ type: "", category_id: "", month: "", q: "", rule_id: "" })}>
                  Clear filters
                </Button>
              </>
            ) : (
              <>
                <p className="font-medium">No transactions yet</p>
                <p className="text-muted-foreground max-w-sm text-sm">
                  Add your first one, like today&apos;s groceries or this month&apos;s salary. Your Overview will update
                  straight away.
                </p>
                <Button onClick={() => setDialogOpen(true)}>
                  <PlusIcon /> Add your first transaction
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="py-0">
          <ul className="divide-y">
            {items.map((t) => (
              <li key={t.id} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{t.description}</p>
                  <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                    <span>{formatDate(t.occurred_on)}</span>
                    <span aria-hidden>·</span>
                    <select
                      aria-label={`Category for ${t.description}`}
                      value={t.category_id ?? ""}
                      onChange={(e) => changeCategory(t, e.target.value)}
                      className="hover:border-input focus-visible:border-ring -ml-1 max-w-44 cursor-pointer rounded border border-transparent bg-transparent px-1 py-0.5 text-xs"
                    >
                      <option value="">No category</option>
                      {categories
                        .filter((c) => c.kind === "transfer" || c.kind === t.type)
                        .map((c) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                    </select>
                    <SourceBadge t={t} />
                    {t.source !== "manual" && <Badge variant="secondary">Imported ({t.source.toUpperCase()})</Badge>}
                  </div>
                </div>
                <span className={`shrink-0 font-semibold tabular-nums ${t.type === "income" ? "text-success" : ""}`}>
                  {t.type === "income" ? "+" : "−"}
                  {formatMoney(t.amount, t.currency)}
                </span>
                <div className="flex shrink-0 gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit ${t.description}`}
                    onClick={() => {
                      setEditing(t);
                      setDialogOpen(true);
                    }}
                  >
                    <PencilIcon />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label={`Delete ${t.description}`} onClick={() => setDeleting(t)}>
                    <Trash2Icon />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {total > PAGE && (
            <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
              <span className="text-muted-foreground">
                {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      <TransactionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        categories={categories}
        editing={editing}
        onSaved={(saved) => {
          load();
          askToLearn(editing, saved);
        }}
      />
      <LearnDialog target={learn} onClose={learned} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete this transaction?"
        description={deleting ? `“${deleting.description}” (${formatMoney(deleting.amount, deleting.currency)}) will be removed for good. Your totals will update.` : ""}
        confirmLabel="Delete"
        onConfirm={async () => {
          if (deleting) await api(`/transactions/${deleting.id}`, undefined, "DELETE");
          setDeleting(null);
          load();
        }}
      />
      <p className="text-muted-foreground mt-6 text-center text-xs">
        Have a bank statement? <Link href="/import" className="underline">Import it</Link> instead of typing every payment.
      </p>
    </>
  );
}

// Shows how the category was chosen, so the user can see learning at work.
function SourceBadge({ t }: { t: Transaction }) {
  if (!t.category_id) return null;
  if (t.category_source === "rule")
    return (
      <Link href="/rules" title={t.category_reason ?? undefined}>
        <Badge variant="success"><WandSparklesIcon className="size-3" /> Your rule</Badge>
      </Link>
    );
  if (t.category_source === "ai")
    return <Badge variant="secondary" title={t.category_reason ?? undefined}><SparklesIcon className="size-3" /> AI</Badge>;
  if (t.category_source === "keyword" && (t.category_confidence ?? 1) < 0.6)
    return <Badge variant="warning" title={t.category_reason ?? undefined}>Please check</Badge>;
  return null;
}
