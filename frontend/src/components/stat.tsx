import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function Stat({ label, value, sub, tone, badge }: { label: string; value: string; sub?: string; tone?: "good" | "bad"; badge?: ReactNode }) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <div className="text-muted-foreground flex items-center justify-between gap-2 text-sm">
          <span>{label}</span>
          {badge}
        </div>
        <p className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "good" && "text-success", tone === "bad" && "text-destructive")}>{value}</p>
        {sub && <p className="text-muted-foreground mt-1 text-xs">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function Progress({ value, tone }: { value: number; tone?: "good" | "warn" | "bad" }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="bg-muted h-2 w-full overflow-hidden rounded-full" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div
        className={cn("h-full rounded-full", tone === "bad" ? "bg-destructive" : tone === "warn" ? "bg-warning" : tone === "good" ? "bg-success" : "bg-primary")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
