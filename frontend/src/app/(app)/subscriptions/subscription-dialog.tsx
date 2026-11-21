"use client";

import { useState } from "react";
import { Alert } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { FREQUENCY_LABELS, todayIso } from "@/lib/format";
import type { Recurring } from "@/lib/types";

// Add a regular payment by hand, or edit one you added. Payments CASIO found
// in your statements keep their amounts and dates from the statements.
type Props = { open: boolean; editing: Recurring | null; onClose: () => void; onSaved: (msg: string) => void };

export function SubscriptionDialog(props: Props) {
  return (
    <Dialog open={props.open} onOpenChange={(o) => !o && props.onClose()}>
      <DialogContent>{props.open && <SubscriptionForm key={props.editing?.id ?? "new"} {...props} />}</DialogContent>
    </Dialog>
  );
}

function SubscriptionForm({ editing, onClose, onSaved }: Props) {
  const [form, setForm] = useState(() =>
    editing
      ? { name: editing.name, kind: editing.kind as string, amount: String(Number(editing.amount)), frequency: editing.frequency as string, next: editing.next_expected_on ?? todayIso() }
      : { name: "", kind: "subscription", amount: "", frequency: "monthly", next: todayIso() },
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return setError("Give it a name.");
    if (!(Number(form.amount) > 0)) return setError("Enter an amount above zero.");
    setBusy(true);
    const body = { name: form.name.trim(), kind: form.kind, amount: Number(form.amount).toFixed(2), frequency: form.frequency, next_payment_on: form.next };
    const r = editing ? await api(`/subscriptions/${editing.id}`, body, "PATCH") : await api("/subscriptions", body);
    setBusy(false);
    if (!r.ok) return setError(r.message);
    onSaved(editing ? `${body.name} updated.` : `${body.name} added.`);
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
        <DialogHeader>
          <DialogTitle>{editing ? "Edit regular payment" : "Add a subscription"}</DialogTitle>
          <DialogDescription>For payments that aren&apos;t in an imported statement yet, like a yearly plan or one paid by card.</DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="sub-name">Name</Label>
            <Input id="sub-name" value={form.name} onChange={set("name")} maxLength={100} placeholder="e.g. JioHotstar" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="sub-amount">Amount (₹)</Label>
              <Input id="sub-amount" type="number" inputMode="decimal" min="0.01" step="0.01" value={form.amount} onChange={set("amount")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sub-freq">How often</Label>
              <NativeSelect id="sub-freq" value={form.frequency} onChange={set("frequency")}>
                {Object.entries(FREQUENCY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sub-kind">Type</Label>
              <NativeSelect id="sub-kind" value={form.kind} onChange={set("kind")}>
                <option value="subscription">Subscription</option>
                <option value="bill">Bill</option>
                <option value="other">Other regular payment</option>
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sub-next">Next payment</Label>
              <Input id="sub-next" type="date" value={form.next} onChange={set("next")} required />
            </div>
          </div>
          {error && <Alert kind="error">{error}</Alert>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : editing ? "Save changes" : "Add subscription"}
            </Button>
          </DialogFooter>
        </form>
    </>
  );
}
