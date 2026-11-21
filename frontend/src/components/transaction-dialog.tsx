"use client";

import { useState } from "react";
import { Alert } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { todayIso } from "@/lib/format";
import type { Category, Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: Category[];
  editing: Transaction | null;
  onSaved: (saved?: Transaction) => void;
};

export function TransactionDialog({ open, onOpenChange, categories, editing, onSaved }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? "Edit transaction" : "Add a transaction"}</DialogTitle>
          <DialogDescription>Record money that came in or went out.</DialogDescription>
        </DialogHeader>
        {/* The form only exists while the dialog is open, so it starts fresh every time. */}
        <TransactionForm categories={categories} editing={editing} onCancel={() => onOpenChange(false)} onSaved={(t) => { onOpenChange(false); onSaved(t); }} />
      </DialogContent>
    </Dialog>
  );
}

function TransactionForm({
  categories,
  editing,
  onCancel,
  onSaved,
}: {
  categories: Category[];
  editing: Transaction | null;
  onCancel: () => void;
  onSaved: (saved?: Transaction) => void;
}) {
  const [type, setType] = useState<"income" | "expense">(editing?.type === "income" ? "income" : "expense");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  // A new id each time the form opens: if "Save" is sent twice, the backend only keeps one.
  const [requestId] = useState(() => crypto.randomUUID());

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      type,
      amount: String(f.get("amount") ?? "").replace(/,/g, "").trim(),
      occurred_on: f.get("occurred_on"),
      description: f.get("description"),
      category_id: f.get("category_id") || null,
      notes: f.get("notes") || null,
      ...(editing ? {} : { client_request_id: requestId }),
    };
    setBusy(true);
    setError("");
    setFields({});
    const res = editing
      ? await api<Transaction>(`/transactions/${editing.id}`, body, "PUT")
      : await api<Transaction>("/transactions", body);
    setBusy(false);
    if (res.ok) onSaved(res.data);
    else {
      setError(res.message);
      setFields(res.fields);
    }
  }

  const options = categories.filter((c) => c.kind === type || c.kind === "transfer");

  return (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {error && <Alert kind="error">{error}</Alert>}
          <div role="radiogroup" aria-label="Type" className="grid grid-cols-2 gap-2">
            {(["expense", "income"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={type === t}
                onClick={() => setType(t)}
                className={cn(
                  "rounded-md border px-3 py-2 text-sm font-medium",
                  type === t ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent",
                )}
              >
                {t === "expense" ? "Money out (expense)" : "Money in (income)"}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="tx-amount">Amount</Label>
              <Input
                id="tx-amount"
                name="amount"
                inputMode="decimal"
                placeholder="0.00"
                defaultValue={editing?.amount ?? ""}
                aria-invalid={!!fields.amount}
                required
              />
              {fields.amount && <p className="text-destructive text-sm">{friendlyAmount(fields.amount)}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tx-date">Date</Label>
              <Input
                id="tx-date"
                name="occurred_on"
                type="date"
                max={todayIso()}
                defaultValue={editing?.occurred_on ?? todayIso()}
                aria-invalid={!!fields.occurred_on}
                required
              />
              {fields.occurred_on && <p className="text-destructive text-sm">{fields.occurred_on}</p>}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tx-desc">Description</Label>
            <Input
              id="tx-desc"
              name="description"
              placeholder={type === "expense" ? "e.g. Groceries at the market" : "e.g. Salary for November"}
              defaultValue={editing?.description ?? ""}
              aria-invalid={!!fields.description}
              maxLength={500}
              required
            />
            {fields.description && <p className="text-destructive text-sm">{fields.description}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tx-cat">Category</Label>
            <NativeSelect id="tx-cat" name="category_id" defaultValue={editing?.category_id ?? ""} key={type}>
              <option value="">Choose later</option>
              {options.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tx-notes">Notes (optional)</Label>
            <Textarea id="tx-notes" name="notes" rows={2} maxLength={2000} defaultValue={editing?.notes ?? ""} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : editing ? "Save changes" : "Add transaction"}
            </Button>
          </DialogFooter>
        </form>
  );
}

export function friendlyAmount(msg: string): string {
  if (/greater than 0/i.test(msg)) return "Enter an amount above zero.";
  if (/decimal places/i.test(msg)) return "Use at most 2 digits after the decimal point.";
  if (/digits/i.test(msg)) return "That amount is too large.";
  if (/valid decimal|required/i.test(msg)) return "Enter an amount, like 250 or 99.50.";
  return msg;
}
