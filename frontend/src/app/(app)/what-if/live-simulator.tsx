"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { RotateCcwIcon } from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import type { Change, SimResult } from "@/lib/planning-types";
import { cn } from "@/lib/utils";

type Inputs = { income: number; spending: number; extra: number; purchase: number };
const ZERO: Inputs = { income: 0, spending: 0, extra: 0, purchase: 0 };
const PRESETS: { label: string; v: Partial<Inputs> }[] = [
  { label: "Income +10%", v: { income: 10 } },
  { label: "Spend 10% less", v: { spending: -10 } },
  { label: "Save ₹5,000 more", v: { extra: 5000 } },
  { label: "Buy a ₹60,000 laptop", v: { purchase: 60000 } },
];

function toChanges(i: Inputs): Change[] {
  const out: Change[] = [];
  if (i.income) out.push({ type: "income_change", percent: i.income });
  if (i.spending) out.push({ type: "spending_change", percent: i.spending });
  if (i.extra) out.push({ type: "extra_saving", amount: i.extra });
  if (i.purchase) out.push({ type: "one_time_expense", amount: i.purchase, label: "Big purchase" });
  return out;
}

const signed = (n: number, c: string) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${formatMoney(Math.abs(n), c)}`;

// Sliders that re-run CASIO's simulator as you move them (debounced). The
// numbers come from the backend's calculation on your usual month.
export function LiveSimulator() {
  const [inputs, setInputs] = useState<Inputs>(ZERO);
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const changes = toChanges(inputs);
    // With no change, simulate "+0%" so the starting point still shows.
    const body = { changes: changes.length ? changes : [{ type: "income_change", percent: 0 }] };
    const id = ++seq.current;
    const t = setTimeout(async () => {
      setBusy(true);
      const r = await api<SimResult>("/what-if", body);
      if (id !== seq.current) return; // a newer request is on its way
      setBusy(false);
      if (r.ok) {
        setResult(r.data);
        setError("");
      } else setError(r.message);
    }, 220);
    return () => clearTimeout(t);
  }, [inputs]);

  const set = (k: keyof Inputs, v: number) => setInputs((i) => ({ ...i, [k]: v }));
  const c = result?.currency ?? "INR";
  const months = result?.projection.slice(0, 6) ?? [];
  const sixDiff = months.length ? Number(months[months.length - 1].scenario) - Number(months[months.length - 1].baseline) : 0;
  const monthDiff = result ? Number(result.difference.surplus) : 0;
  const maxAbs = Math.max(1, ...months.flatMap((m) => [Math.abs(Number(m.baseline)), Math.abs(Number(m.scenario))]));
  const active = toChanges(inputs).length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Live simulator <BasisBadge basis="forecast" />
          {busy && <span className="text-muted-foreground text-xs font-normal">Recalculating…</span>}
        </CardTitle>
        <CardDescription>Move a slider and the result updates. Your real data is not changed.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <Button key={p.label} type="button" size="sm" variant="outline" onClick={() => setInputs({ ...ZERO, ...p.v })}>
                {p.label}
              </Button>
            ))}
            <Button type="button" size="sm" variant="ghost" onClick={() => setInputs(ZERO)} disabled={!active}>
              <RotateCcwIcon /> Reset
            </Button>
          </div>
          <Slider id="s-income" label="Income" value={inputs.income} min={-30} max={50} step={5} fmt={(v) => `${v > 0 ? "+" : ""}${v}%`} onChange={(v) => set("income", v)} />
          <Slider id="s-spend" label="All spending" value={inputs.spending} min={-50} max={30} step={5} fmt={(v) => `${v > 0 ? "+" : ""}${v}%`} onChange={(v) => set("spending", v)} />
          <Slider id="s-extra" label="Save extra each month (for goals)" value={inputs.extra} min={0} max={20000} step={500} fmt={(v) => formatMoney(v, c)} onChange={(v) => set("extra", v)} />
          <Slider id="s-buy" label="One-off purchase next month" value={inputs.purchase} min={0} max={200000} step={5000} fmt={(v) => formatMoney(v, c)} onChange={(v) => set("purchase", v)} />
        </div>

        <div className="space-y-4" aria-live="polite">
          {error && <Alert kind="error">{error}</Alert>}
          {result && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Figure label="Left each month" value={formatMoney(result.scenario.surplus, c)} sub={monthDiff ? `${signed(monthDiff, c)} vs now` : "same as now"} tone={monthDiff} />
                <Figure
                  label="Savings after 6 months"
                  value={signed(sixDiff, c)}
                  sub={inputs.extra && !sixDiff ? "same total: the extra goes into your goals" : "compared with no change"}
                  tone={sixDiff}
                />
              </div>
              <div>
                <p className="text-muted-foreground mb-2 text-xs">Savings path, next 6 months (grey: as now, colour: with change)</p>
                <div className="flex h-36 items-end gap-2" role="img" aria-label="Six-month savings comparison">
                  {months.map((m) => (
                    <div key={m.month} className="flex flex-1 flex-col items-center gap-1">
                      <div className="flex h-28 w-full items-end gap-1">
                        <span className="bg-muted-foreground/30 flex-1 rounded-t transition-[height] duration-500" style={{ height: `${(Math.max(0, Number(m.baseline)) / maxAbs) * 100}%` } as CSSProperties} />
                        <span
                          className={cn("flex-1 rounded-t transition-[height] duration-500", Number(m.scenario) >= Number(m.baseline) ? "bg-success" : "bg-destructive")}
                          style={{ height: `${(Math.max(0, Number(m.scenario)) / maxAbs) * 100}%` } as CSSProperties}
                        />
                      </div>
                      <span className="text-muted-foreground text-[0.68rem]">{formatMonth(m.month).split(" ")[0]}</span>
                    </div>
                  ))}
                </div>
              </div>
              {result.goals.length > 0 && active && (
                <ul className="space-y-1 text-sm">
                  {result.goals.map((g) => (
                    <li key={g.id} className="flex justify-between gap-3">
                      <span>{g.name}</span>
                      <span className="text-muted-foreground tabular-nums">
                        {g.months_sooner_or_later ? `${Math.abs(g.months_sooner_or_later)} month${Math.abs(g.months_sooner_or_later) === 1 ? "" : "s"} ${g.months_sooner_or_later > 0 ? "later" : "sooner"}` : "no change"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-muted-foreground text-xs">{result.explanation[active ? 1 : 0] ?? result.explanation[0]}</p>
            </>
          )}
          {!result && !error && <p className="text-muted-foreground text-sm">Working out your usual month…</p>}
        </div>
      </CardContent>
    </Card>
  );
}

function Slider({ id, label, value, min, max, step, fmt, onChange }: { id: string; label: string; value: number; min: number; max: number; step: number; fmt: (v: number) => string; onChange: (v: number) => void }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <span className="text-sm font-semibold tabular-nums">{fmt(value)}</span>
      </div>
      <input id={id} type="range" className="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={fmt(value)} />
    </div>
  );
}

function Figure({ label, value, sub, tone }: { label: string; value: string; sub: string; tone: number }) {
  return (
    <div className="bg-muted rounded-lg p-3">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={cn("font-display mt-0.5 text-2xl font-semibold tabular-nums", tone > 0 && "text-success", tone < 0 && "text-destructive")}>{value}</p>
      <p className="text-muted-foreground text-xs">{sub}</p>
    </div>
  );
}
