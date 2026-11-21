"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeftIcon, CheckCircle2Icon, ChevronDownIcon, SparklesIcon, WandSparklesIcon } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
import { LearnDialog, type LearnResult, type LearnTarget } from "@/components/learn-dialog";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { Category, ImportBatch, ImportDetail, ImportRow } from "@/lib/types";

type Filter = "all" | "fix" | "check" | "dupes";
type Patch = Partial<Pick<ImportRow, "occurred_on" | "description" | "amount" | "type" | "category_id" | "include">> & {
  apply_to_similar?: boolean;
};

const AI_NOTE: Record<string, { kind: "info" | "error"; text: string } | null> = {
  used: { kind: "info", text: "AI suggested categories for the descriptions CASIO's own rules weren't sure about. Only the description text was shared, never names, account numbers or amounts." },
  not_configured: { kind: "info", text: "Categories were chosen with CASIO's built-in rules. Rows marked “Please check” are guesses; pick the right category and CASIO will use it." },
  failed: { kind: "error", text: "The AI helper couldn't be reached, so CASIO's built-in rules chose the categories. Nothing else is affected." },
  not_needed: null,
};

export function ReviewView({ batchId }: { batchId: string }) {
  const router = useRouter();
  const [batch, setBatch] = useState<ImportDetail | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<ImportBatch | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [learn, setLearn] = useState<LearnTarget | null>(null);
  const [ruleNote, setRuleNote] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  useEffect(() => {
    api<ImportDetail>(`/imports/${batchId}`).then((r) => (r.ok ? setBatch(r.data) : setError(r.message)));
    api<Category[]>("/categories").then((r) => r.ok && setCategories(r.data));
  }, [batchId]);

  const rows = useMemo(() => batch?.rows ?? [], [batch]);
  const counts = useMemo(
    () => ({
      ticked: rows.filter((r) => r.include).length,
      fix: rows.filter((r) => r.include && r.problems.length).length,
      check: rows.filter((r) => r.needs_check).length,
      dupes: rows.filter((r) => r.duplicate_kind).length,
    }),
    [rows],
  );
  const visible = rows.filter((r) =>
    filter === "fix" ? r.problems.length > 0 : filter === "check" ? r.needs_check : filter === "dupes" ? !!r.duplicate_kind : true,
  );

  function merge(updated: ImportRow[]) {
    setBatch((b) => b && { ...b, rows: b.rows.map((r) => updated.find((u) => u.id === r.id) ?? r) });
  }

  async function patch(row: ImportRow, body: Patch): Promise<boolean> {
    setSaveError("");
    const r = await api<ImportRow[]>(`/imports/${batchId}/rows/${row.id}`, body, "PATCH");
    if (!r.ok) {
      setSaveError(Object.values(r.fields)[0] ?? r.message);
      return false;
    }
    merge(r.data);
    return true;
  }

  // Save the new category on this row, then ask whether CASIO should reuse it.
  async function changeCategory(row: ImportRow, categoryId: string) {
    const ok = await patch(row, { category_id: categoryId || null });
    if (ok && categoryId)
      setLearn({ kind: "import_row", id: row.id, description: row.description, categoryId, fromCategory: row.category_name });
  }

  async function learned(result: LearnResult) {
    const target = learn;
    setLearn(null);
    if (!target) return;
    if (result.choice === "similar") {
      const row = rows.find((r) => r.id === target.id);
      if (row) await patch(row, { category_id: target.categoryId, apply_to_similar: true });
    } else if (result.choice === "rule") {
      const s = result.saved;
      setRuleNote(
        `Rule made: “${s.rule.pattern}” → ${s.rule.category_name}. ${s.changed_import_rows} other row${s.changed_import_rows === 1 ? "" : "s"} here` +
          (s.changed_transactions ? ` and ${s.changed_transactions} saved transaction${s.changed_transactions === 1 ? "" : "s"}` : "") +
          " now use it. Manage it under Learned Rules.",
      );
      const r = await api<ImportDetail>(`/imports/${batchId}`);
      if (r.ok) setBatch(r.data);
    }
  }

  async function bulk(include: boolean, which: "all" | "duplicates" | "ready") {
    const r = await api<ImportDetail>(`/imports/${batchId}/include`, { include, which });
    if (r.ok) setBatch(r.data);
  }

  async function save() {
    setSaving(true);
    setSaveError("");
    const r = await api<ImportBatch>(`/imports/${batchId}/confirm`, {});
    setSaving(false);
    if (r.ok) setSaved(r.data);
    else setSaveError(r.message);
  }

  if (error)
    return (
      <>
        <BackLink />
        <Alert kind="error">{error}</Alert>
      </>
    );
  if (!batch) return <p className="text-muted-foreground py-10 text-center text-sm">Loading…</p>;

  if (saved)
    return (
      <Card className="mx-auto max-w-lg">
        <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
          <CheckCircle2Icon className="text-success size-12" />
          <h1 className="text-xl font-semibold">Saved {saved.rows_imported} transactions</h1>
          <p className="text-muted-foreground text-sm">
            Your Overview and Transactions now include them. Each one remembers it came from{" "}
            {batch.original_filename ? `“${batch.original_filename}”` : "your pasted SMS"}. You can undo the whole import from the
            Import page.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild><Link href="/overview">See Overview</Link></Button>
            <Button variant="outline" asChild><Link href="/transactions">View transactions</Link></Button>
            <Button variant="ghost" asChild><Link href="/import">Import another</Link></Button>
          </div>
        </CardContent>
      </Card>
    );

  const reviewing = batch.status === "needs_review";
  const aiNote = batch.ai_status ? AI_NOTE[batch.ai_status] : null;
  const where = (r: ImportRow) =>
    r.row_number == null ? null : batch.source_type === "csv" ? `Line ${r.row_number}` : batch.source_type === "pdf" ? `Page ${r.row_number}` : `Message ${r.row_number}`;

  return (
    <>
      <BackLink />
      <PageHeader
        title="Check before saving"
        description={`${batch.original_filename ?? "Pasted SMS messages"} · ${batch.source_type.toUpperCase()}. Nothing is saved until you press Save. Fix anything that's wrong; untick rows you don't want.`}
      />

      {!reviewing && <div className="mb-4"><Alert kind="info">This import has already been saved or cancelled.</Alert></div>}

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Found" value={rows.length} />
        <Stat label="Ticked to save" value={counts.ticked} />
        <Stat label="Need fixing" value={counts.fix} tone={counts.fix ? "bad" : undefined} />
        <Stat label="Categories to check" value={counts.check} tone={counts.check ? "warn" : undefined} />
      </div>

      <div className="mb-4 space-y-2">
        {aiNote && (
          <Alert kind={aiNote.kind}>
            <span className="inline-flex items-start gap-1.5">{batch.ai_status === "used" && <SparklesIcon className="mt-0.5 size-4 shrink-0" />}{aiNote.text}</span>
          </Alert>
        )}
        {ruleNote && (
          <Alert kind="success">
            <span className="inline-flex items-start gap-1.5"><WandSparklesIcon className="mt-0.5 size-4 shrink-0" />{ruleNote}</span>
          </Alert>
        )}
        {(batch.warnings ?? []).map((w) => (
          <Alert key={w} kind="info">{w}</Alert>
        ))}
        {batch.errors.length > 0 && (
          <div className="rounded-lg border px-4 py-3 text-sm">
            <button className="flex w-full items-center justify-between font-medium" onClick={() => setShowErrors((s) => !s)} aria-expanded={showErrors}>
              {batch.errors.length} {batch.errors.length === 1 ? "line" : "lines"} couldn&apos;t be read and {batch.errors.length === 1 ? "was" : "were"} skipped
              <ChevronDownIcon className={`size-4 transition-transform ${showErrors ? "rotate-180" : ""}`} />
            </button>
            {showErrors && (
              <ul className="mt-2 space-y-2">
                {batch.errors.map((e, i) => (
                  <li key={i}>
                    <p>{e.row_number != null && <span className="text-muted-foreground">Line {e.row_number}: </span>}{e.message}</p>
                    {e.raw_text && <code className="bg-muted mt-1 block rounded px-2 py-1 text-xs break-all">{e.raw_text}</code>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {(
          [
            ["all", `All (${rows.length})`],
            ["fix", `Need fixing (${rows.filter((r) => r.problems.length).length})`],
            ["check", `Check category (${counts.check})`],
            ["dupes", `Possible duplicates (${counts.dupes})`],
          ] as const
        ).map(([key, label]) => (
          <Button key={key} size="sm" variant={filter === key ? "default" : "outline"} onClick={() => setFilter(key)}>
            {label}
          </Button>
        ))}
        {reviewing && (
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => bulk(true, "all")}>Tick all</Button>
            <Button size="sm" variant="ghost" onClick={() => bulk(false, "all")}>Untick all</Button>
          </div>
        )}
      </div>

      <Card className="py-0">
        <div className="text-muted-foreground hidden border-b px-4 py-2 text-xs font-medium lg:grid lg:grid-cols-[1.5rem_9.5rem_minmax(0,1fr)_8rem_8.5rem_13rem] lg:gap-3">
          <span aria-hidden />
          <span>Date</span>
          <span>Description</span>
          <span>Amount</span>
          <span>In / out</span>
          <span>Category</span>
        </div>
        {visible.length === 0 ? (
          <p className="text-muted-foreground px-4 py-8 text-center text-sm">Nothing here. 🎉</p>
        ) : (
          <ul className="divide-y">
            {visible.map((r) => (
              <RowEditor
                key={r.id}
                row={r}
                where={where(r)}
                categories={categories}
                disabled={!reviewing}
                onPatch={(body) => patch(r, body)}
                onCategory={(id) => changeCategory(r, id)}
              />
            ))}
          </ul>
        )}
      </Card>

      {reviewing && (
        <div className="bg-background/95 sticky bottom-0 z-10 mt-4 -mx-4 border-t px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
          {saveError && <div className="mb-2"><Alert kind="error">{saveError}</Alert></div>}
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm">
              <strong>{counts.ticked}</strong> of {rows.length} ticked
              {counts.fix > 0 && <span className="text-destructive"> · {counts.fix} still need fixing</span>}
            </p>
            <div className="ml-auto flex gap-2">
              <Button variant="outline" onClick={() => setCancelOpen(true)}>Cancel import</Button>
              <Button onClick={save} disabled={saving || counts.ticked === 0 || counts.fix > 0}>
                {saving ? "Saving…" : `Save ${counts.ticked} transaction${counts.ticked === 1 ? "" : "s"}`}
              </Button>
            </div>
          </div>
        </div>
      )}

      <LearnDialog target={learn} onClose={learned} />

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancel this import?"
        description="Nothing from this file will be saved. Your fixes on this screen will be lost. You can upload the file again later."
        confirmLabel="Cancel import"
        onConfirm={async () => {
          await api(`/imports/${batchId}`, undefined, "DELETE");
          router.push("/import");
        }}
      />
    </>
  );
}

function BackLink() {
  return (
    <Link href="/import" className="text-muted-foreground hover:text-foreground mb-3 inline-flex items-center gap-1 text-sm">
      <ArrowLeftIcon className="size-4" /> Import Statements
    </Link>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "bad" | "warn" }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={`text-xl font-semibold tabular-nums ${tone === "bad" ? "text-destructive" : tone === "warn" ? "text-warning" : ""}`}>{value}</p>
    </div>
  );
}

function ConfidenceBadge({ row }: { row: ImportRow }) {
  if (!row.category_id) return <Badge variant="warning">Please choose</Badge>;
  if (row.category_source === "user") return <Badge variant="secondary">You chose</Badge>;
  if (row.category_source === "rule")
    return (
      <Badge variant="success" title={row.category_reason ?? undefined}>
        <WandSparklesIcon className="size-3" /> Your rule · {Math.round((row.category_confidence ?? 0) * 100)}%
      </Badge>
    );
  const pct = Math.round((row.category_confidence ?? 0) * 100);
  const who = row.category_source === "ai" ? "AI" : "Auto";
  if (row.needs_check) return <Badge variant="warning" title={row.category_reason ?? undefined}>{who} · {pct}% · Please check</Badge>;
  return (
    <Badge variant={pct >= 80 ? "success" : "secondary"} title={row.category_reason ?? undefined}>
      {who} · {pct}% sure
    </Badge>
  );
}

function RowEditor({
  row,
  where,
  categories,
  disabled,
  onPatch,
  onCategory,
}: {
  row: ImportRow;
  where: string | null;
  categories: Category[];
  disabled: boolean;
  onPatch: (body: Patch) => Promise<boolean>;
  onCategory: (id: string) => void;
}) {
  const [desc, setDesc] = useState(row.description);
  const [amount, setAmount] = useState(row.amount ?? "");
  const [amountError, setAmountError] = useState("");
  const [showRaw, setShowRaw] = useState(false);
  // Keep the inputs in step when the server changes the row (e.g. "change similar rows").
  const [seen, setSeen] = useState(row);
  if (seen !== row) {
    setSeen(row);
    setDesc(row.description);
    setAmount(row.amount ?? "");
  }
  const fitting = categories.filter((c) => c.kind === "transfer" || c.kind === (row.type ?? "expense"));

  return (
    <li className={`px-4 py-3 ${row.include ? "" : "bg-muted/40"}`}>
      <div className="grid grid-cols-[1.5rem_1fr] gap-3 lg:grid-cols-[1.5rem_9.5rem_minmax(0,1fr)_8rem_8.5rem_13rem] lg:items-start">
        <Checkbox
          className="mt-3"
          checked={row.include}
          disabled={disabled}
          onCheckedChange={(v) => onPatch({ include: v === true })}
          aria-label={`Save “${row.description}”`}
        />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:contents">
          <Input
            type="date"
            aria-label="Date"
            aria-invalid={!row.occurred_on}
            disabled={disabled}
            defaultValue={row.occurred_on ?? ""}
            key={`d-${row.occurred_on}`}
            onBlur={(e) => e.target.value && e.target.value !== row.occurred_on && onPatch({ occurred_on: e.target.value })}
          />
          <div className="col-span-2 min-w-0 sm:col-span-3 lg:col-span-1">
            <Input
              aria-label="Description"
              disabled={disabled}
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              onBlur={() => desc.trim() && desc !== row.description && onPatch({ description: desc })}
            />
          </div>
          <div>
            <Input
              aria-label="Amount"
              inputMode="decimal"
              aria-invalid={!row.amount || !!amountError}
              disabled={disabled}
              value={amount}
              placeholder="0.00"
              onChange={(e) => setAmount(e.target.value)}
              onBlur={async () => {
                const clean = amount.replace(/[,₹\s]/g, "");
                if (!clean || clean === row.amount) return setAmountError("");
                if (!/^\d+(\.\d{1,2})?$/.test(clean) || Number(clean) <= 0) return setAmountError("Enter an amount like 450.00");
                setAmountError("");
                if (await onPatch({ amount: clean })) setAmount(clean);
              }}
            />
            {amountError && <p className="text-destructive mt-1 text-xs">{amountError}</p>}
          </div>
          <NativeSelect
            aria-label="Money in or out"
            aria-invalid={!row.type}
            disabled={disabled}
            value={row.type ?? ""}
            onChange={(e) => e.target.value && onPatch({ type: e.target.value as "income" | "expense" })}
          >
            {!row.type && <option value="">Choose…</option>}
            <option value="expense">Money out</option>
            <option value="income">Money in</option>
          </NativeSelect>
          <div className="col-span-2 space-y-1 sm:col-span-4 lg:col-span-1">
            <NativeSelect aria-label="Category" disabled={disabled} value={row.category_id ?? ""} onChange={(e) => onCategory(e.target.value)}>
              <option value="">No category</option>
              {fitting.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </NativeSelect>
            <ConfidenceBadge row={row} />
          </div>
        </div>
      </div>

      <div className="mt-2 space-y-1 pl-9 text-xs">
        {row.problems.map((p) => (
          <p key={p} className="text-destructive font-medium">{p}</p>
        ))}
        {row.duplicate_note && <p className="text-warning">{row.duplicate_note}</p>}
        <p className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1">
          {row.amount && row.type && (
            <span className={row.type === "income" ? "text-success" : ""}>
              {row.type === "income" ? "+" : "−"}
              {formatMoney(row.amount)}
            </span>
          )}
          {row.category_reason && row.category_source !== "user" && <span>· Why: {row.category_reason}</span>}
          {row.balance_after && <span>· Balance after: {formatMoney(row.balance_after)}</span>}
          {where && <span>· {where}</span>}
          {row.edited && <Badge variant="outline">Edited</Badge>}
          <button className="text-primary hover:underline" onClick={() => setShowRaw((s) => !s)} aria-expanded={showRaw}>
            {showRaw ? "Hide original" : "Show original"}
          </button>
        </p>
        {showRaw && <code className="bg-muted block rounded px-2 py-1 break-all whitespace-pre-wrap">{row.raw_text}</code>}
      </div>
    </li>
  );
}
