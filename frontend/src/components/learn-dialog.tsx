"use client";

import { useEffect, useState } from "react";
import { SparklesIcon, TriangleAlertIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Priority, RulePreview, RuleSave } from "@/lib/types";
import { cn } from "@/lib/utils";

// What the user just changed. The category is already saved on that one
// item; this dialog only decides whether CASIO should reuse the choice.
export type LearnTarget = {
  kind: "transaction" | "import_row";
  id: string;
  description: string;
  categoryId: string;
  fromCategory: string | null;
};

export type LearnResult = { choice: "once" } | { choice: "similar" } | { choice: "rule"; saved: RuleSave };

type Choice = "once" | "similar" | "always";

export function LearnDialog({ target, onClose }: { target: LearnTarget | null; onClose: (result: LearnResult) => void }) {
  return (
    <Dialog open={target !== null} onOpenChange={(o) => !o && onClose({ choice: "once" })}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        {target && <LearnForm key={`${target.id}-${target.categoryId}`} target={target} onClose={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function LearnForm({ target, onClose }: { target: LearnTarget; onClose: (result: LearnResult) => void }) {
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const [error, setError] = useState("");
  const [choice, setChoice] = useState<Choice | null>(null);
  const [applyPast, setApplyPast] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const [matchType, setMatchType] = useState<"merchant" | "contains" | null>(null);
  const [pattern, setPattern] = useState<string | null>(null);
  const [priority, setPriority] = useState<Priority>("normal");
  const [busy, setBusy] = useState(false);

  // Ask the backend what a rule would do. Runs again (after a pause) when the
  // user edits how the rule matches.
  useEffect(() => {
    const body = {
      [target.kind === "transaction" ? "transaction_id" : "import_row_id"]: target.id,
      category_id: target.categoryId,
      ...(matchType ? { match_type: matchType } : {}),
      ...(pattern !== null ? { pattern } : {}),
    };
    const t = setTimeout(async () => {
      const r = await api<RulePreview>("/rules/preview", body);
      if (!r.ok) return setError(r.message);
      setError("");
      setPreview(r.data);
      setChoice((c) => c ?? (r.data.recommendation === "always" && !r.data.pattern_problem ? "always" : "once"));
    }, pattern === null && matchType === null ? 0 : 400);
    return () => clearTimeout(t);
  }, [target, matchType, pattern]);

  async function done() {
    if (!preview || !choice) return;
    if (choice === "once") return onClose({ choice: "once" });
    if (choice === "similar") return onClose({ choice: "similar" });
    setBusy(true);
    const r = await api<RuleSave>("/rules", {
      category_id: target.categoryId,
      match_type: preview.match_type,
      pattern: preview.pattern,
      applies_to: preview.tx_type,
      priority,
      apply_to_past: applyPast,
      source_transaction_id: target.kind === "transaction" ? target.id : null,
    });
    setBusy(false);
    if (r.ok) onClose({ choice: "rule", saved: r.data });
    else setError(r.message);
  }

  const p = preview;
  const what = p ? (p.match_type === "merchant" ? `shop name “${p.pattern}”` : `descriptions containing “${p.pattern}”`) : "";
  const thing = target.kind === "transaction" ? "transaction" : "row";

  return (
    <>
      <DialogHeader>
        <DialogTitle>Remember this for next time?</DialogTitle>
        <DialogDescription>
          You changed “{target.description}”{target.fromCategory ? ` from ${target.fromCategory}` : ""} to{" "}
          <strong className="text-foreground">{p?.category_name ?? "…"}</strong>. That&apos;s saved. Should CASIO do the same for
          similar transactions?
        </DialogDescription>
      </DialogHeader>

      {error && <Alert kind="error">{error}</Alert>}
      {!p ? (
        <p className="text-muted-foreground py-6 text-center text-sm">Checking your transactions…</p>
      ) : (
        <div className="space-y-3">
          <div className="bg-primary/5 border-primary/20 flex gap-2 rounded-lg border px-3 py-2 text-sm">
            <SparklesIcon className="text-primary mt-0.5 size-4 shrink-0" />
            <p>
              <span className="font-medium">CASIO suggests: {p.recommendation === "always" ? "make a rule" : "just this one"}.</span>{" "}
              {p.reason}
            </p>
          </div>

          <div role="radiogroup" aria-label="What should CASIO remember?" className="space-y-2">
            <Option checked={choice === "once"} onSelect={() => setChoice("once")} title={`Just this ${thing}`}>
              Pick this when it was a one-off. Nothing else changes.
            </Option>

            {target.kind === "import_row" && p.matching_in_import > 0 && (
              <Option checked={choice === "similar"} onSelect={() => setChoice("similar")} title={`Only similar rows in this file (${p.matching_in_import})`}>
                Changes the rows in this import that look the same, but doesn&apos;t make a rule for the future.
              </Option>
            )}

            <Option
              checked={choice === "always"}
              onSelect={() => !p.pattern_problem && setChoice("always")}
              disabled={!!p.pattern_problem}
              title={`Always use ${p.category_name} for ${what || "this shop"}`}
            >
              {p.pattern_problem ? (
                <span className="text-warning">{p.pattern_problem}</span>
              ) : (
                <>
                  CASIO makes a rule and uses it on future imports and new transactions
                  {p.matching_in_import > 0 ? `, and on ${p.matching_in_import} other row${p.matching_in_import === 1 ? "" : "s"} in this file` : ""}.
                  Categories you picked yourself are never changed. You can edit or remove the rule any time.
                </>
              )}
            </Option>
          </div>

          {choice === "always" && !p.pattern_problem && (
            <div className="space-y-3 rounded-lg border px-3 py-3 text-sm">
              {p.matching_past > 0 ? (
                <div>
                  <label className="flex items-start gap-2">
                    <Checkbox checked={applyPast} onCheckedChange={(v) => setApplyPast(v === true)} className="mt-0.5" />
                    <span>
                      Also change <strong>{p.matching_past}</strong> earlier transaction{p.matching_past === 1 ? "" : "s"} to {p.category_name}
                    </span>
                  </label>
                  <ul className="text-muted-foreground mt-2 space-y-1 pl-6 text-xs">
                    {p.examples.map((e, i) => (
                      <li key={i} className="truncate">
                        {formatDate(e.occurred_on)} · {e.description} · {formatMoney(e.amount)} · now {e.category_name ?? "no category"}
                      </li>
                    ))}
                    {p.matching_past > p.examples.length && <li>and {p.matching_past - p.examples.length} more</li>}
                  </ul>
                </div>
              ) : (
                <p className="text-muted-foreground">No earlier transactions need changing.</p>
              )}

              {p.existing_rule && !p.existing_rule.same_category && (
                <Warn>This replaces your rule that sends {what} to {p.existing_rule.category_name}.</Warn>
              )}
              {p.overlaps.map((o) => (
                <Warn key={o.id}>
                  Your rule “{o.pattern}” → {o.category_name} also matches this.{" "}
                  {o.wins ? "It has higher priority, so it will still win here. Raise this rule's priority below to change that." : "The new rule is more specific, so it wins."}
                </Warn>
              ))}

              <button type="button" className="text-primary text-xs font-medium hover:underline" onClick={() => setAdvanced((a) => !a)} aria-expanded={advanced}>
                {advanced ? "Hide matching options" : "Change how it matches"}
              </button>
              {advanced && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="learn-match">Match</Label>
                    <NativeSelect
                      id="learn-match"
                      value={p.match_type}
                      onChange={(e) => {
                        const m = e.target.value as "merchant" | "contains";
                        setMatchType(m);
                        setPattern(m === "merchant" ? (p.merchant_key ?? p.suggested_word) : p.suggested_word);
                      }}
                    >
                      <option value="merchant">Shop name starts with</option>
                      <option value="contains">Description contains</option>
                    </NativeSelect>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="learn-pattern">Words</Label>
                    <Input id="learn-pattern" value={pattern ?? p.pattern} onChange={(e) => setPattern(e.target.value)} maxLength={100} />
                  </div>
                  <div className="space-y-1.5 sm:col-span-2">
                    <Label htmlFor="learn-priority">Priority when rules disagree</Label>
                    <NativeSelect id="learn-priority" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
                      <option value="high">High: wins over other rules</option>
                      <option value="normal">Normal: the more specific rule wins</option>
                      <option value="low">Low: only if no other rule matches</option>
                    </NativeSelect>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <DialogFooter>
        <Button onClick={done} disabled={!p || !choice || busy || (choice === "always" && !!p?.pattern_problem)}>
          {busy ? "Saving…" : choice === "always" ? "Make the rule" : "Done"}
        </Button>
      </DialogFooter>
    </>
  );
}

function Option({
  checked,
  onSelect,
  title,
  children,
  disabled,
}: {
  checked: boolean;
  onSelect: () => void;
  title: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      aria-disabled={disabled}
      onClick={onSelect}
      className={cn(
        "flex w-full gap-3 rounded-lg border px-3 py-2.5 text-left text-sm",
        checked ? "border-primary bg-primary/5" : "hover:bg-accent",
        disabled && "cursor-not-allowed opacity-70",
      )}
    >
      <span className={cn("mt-0.5 size-4 shrink-0 rounded-full border-2", checked ? "border-primary border-[5px]" : "border-muted-foreground/40")} aria-hidden />
      <span>
        <span className="block font-medium">{title}</span>
        <span className="text-muted-foreground block text-xs">{children}</span>
      </span>
    </button>
  );
}

function Warn({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-warning flex gap-1.5 text-xs">
      <TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
