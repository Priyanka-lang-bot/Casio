"use client";

import { useEffect, useState } from "react";
import { PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
import { friendlyAmount } from "@/components/transaction-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";

export type FieldDef = {
  name: string;
  label: string;
  type: "text" | "money" | "percent" | "select";
  options?: Record<string, string>;
  optional?: boolean;
  placeholder?: string;
  defaultValue?: string; // for selects; otherwise the first option
};

type Item = Record<string, string | null> & { id: string };

// A reusable "list + add/edit/delete" card for one kind of profile entry.
export function EntityList({
  title,
  description,
  endpoint,
  noun,
  fields,
  renderSummary,
  emptyText,
  onChange,
}: {
  title: string;
  description: string;
  endpoint: string;
  noun: string;
  fields: FieldDef[];
  renderSummary: (item: Item) => React.ReactNode;
  emptyText: string;
  onChange: () => void;
}) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [editing, setEditing] = useState<Item | "new" | null>(null);
  const [deleting, setDeleting] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const load = async () => {
    const r = await api<Item[]>(endpoint);
    if (r.ok) setItems(r.data);
  };
  useEffect(() => {
    let alive = true;
    api<Item[]>(endpoint).then((r) => alive && r.ok && setItems(r.data));
    return () => {
      alive = false;
    };
  }, [endpoint]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, string | null> = {};
    for (const fd of fields) {
      let v = String(f.get(fd.name) ?? "").trim();
      if (fd.type === "money" || fd.type === "percent") v = v.replace(/,/g, "");
      body[fd.name] = v === "" && fd.optional ? null : v;
    }
    setBusy(true);
    setError("");
    setFieldErrors({});
    const r = editing === "new" ? await api(endpoint, body) : await api(`${endpoint}/${(editing as Item).id}`, body, "PUT");
    setBusy(false);
    if (r.ok) {
      setEditing(null);
      await load();
      onChange();
    } else {
      setError(r.message);
      setFieldErrors(r.fields);
    }
  }

  const current = editing && editing !== "new" ? editing : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        <CardAction>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setError("");
              setFieldErrors({});
              setEditing("new");
            }}
          >
            <PlusIcon /> Add
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {items === null ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-muted-foreground rounded-md border border-dashed p-4 text-center text-sm">{emptyText}</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-2 px-3 py-2.5">
                <div className="min-w-0 flex-1 text-sm">{renderSummary(item)}</div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Edit ${item.name}`}
                  onClick={() => {
                    setError("");
                    setFieldErrors({});
                    setEditing(item);
                  }}
                >
                  <PencilIcon />
                </Button>
                <Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={() => setDeleting(item)}>
                  <Trash2Icon />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{current ? `Edit ${noun}` : `Add ${noun}`}</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} noValidate className="space-y-4" key={current?.id ?? "new"}>
            {error && <Alert kind="error">{error}</Alert>}
            {fields.map((fd) => {
              const id = `${endpoint}-${fd.name}`;
              const err = fieldErrors[fd.name];
              const value = current?.[fd.name] ?? "";
              return (
                <div key={fd.name} className="space-y-1.5">
                  <Label htmlFor={id}>
                    {fd.label}
                    {fd.optional && <span className="text-muted-foreground font-normal">(optional)</span>}
                  </Label>
                  {fd.type === "select" ? (
                    <NativeSelect id={id} name={fd.name} defaultValue={value || fd.defaultValue || Object.keys(fd.options!)[0]}>
                      {Object.entries(fd.options!).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : (
                    <Input
                      id={id}
                      name={fd.name}
                      defaultValue={value}
                      placeholder={fd.placeholder}
                      inputMode={fd.type === "text" ? undefined : "decimal"}
                      aria-invalid={!!err}
                      maxLength={fd.type === "text" ? 100 : 20}
                    />
                  )}
                  {err && <p className="text-destructive text-sm">{fd.type === "text" ? err : friendlyAmount(err)}</p>}
                </div>
              );
            })}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete this ${noun}?`}
        description={deleting ? `“${deleting.name}” will be removed from your profile.` : ""}
        confirmLabel="Delete"
        onConfirm={async () => {
          if (deleting) await api(`${endpoint}/${deleting.id}`, undefined, "DELETE");
          setDeleting(null);
          await load();
          onChange();
        }}
      />
    </Card>
  );
}
