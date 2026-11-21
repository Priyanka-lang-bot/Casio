"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PencilIcon, PlusIcon, ReceiptIcon, Trash2Icon } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
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
import type { Category, Transaction } from "@/lib/types";

const PAGE = 50;

export function TransactionsView() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<Transaction[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ type: "", category_id: "", month: "", q: "" });
  const [offset, setOffset] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [deleting, setDeleting] = useState<Transaction | null>(null);

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

  const setFilter = (k: keyof typeof filters, v: string) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v }));
  };
  const filtering = Object.values(filters).some(Boolean);

  return (
    <>
      <PageHeader
        title="Transactions"
        description="Every payment in and out. Add them by hand for now; statement import is coming next."
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

      {items === null ? (
        <p className="text-muted-foreground py-10 text-center text-sm">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <ReceiptIcon className="text-muted-foreground size-10" />
            {filtering ? (
              <>
                <p className="font-medium">No transactions match these filters.</p>
                <Button variant="outline" onClick={() => setFilters({ type: "", category_id: "", month: "", q: "" })}>
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
                    {t.category_name ? <span>{t.category_name}</span> : <Badge variant="outline">No category</Badge>}
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
        onSaved={load}
      />
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
        Have a bank statement? <Link href="/import" className="underline">Statement import</Link> is the next feature being built.
      </p>
    </>
  );
}
