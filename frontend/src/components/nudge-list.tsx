"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangleIcon, InfoIcon, PartyPopperIcon, SirenIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Nudge } from "@/lib/planning-types";
import { cn } from "@/lib/utils";

const ICON = { critical: SirenIcon, warning: AlertTriangleIcon, info: InfoIcon, good: PartyPopperIcon };
const TONE = {
  critical: "border-destructive/30 bg-destructive/5",
  warning: "border-warning/30 bg-warning/5",
  info: "border-border bg-card",
  good: "border-success/30 bg-success/5",
};

// Proactive nudges, re-checked by the backend every time this loads.
export function NudgeList({ limit = 5, filter, emptyText }: { limit?: number; filter?: (n: Nudge) => boolean; emptyText?: string }) {
  const [items, setItems] = useState<Nudge[] | null>(null);

  useEffect(() => {
    api<Nudge[]>(`/nudges?limit=20`).then((r) => r.ok && setItems(r.data));
  }, []);

  if (!items) return null;
  const shown = (filter ? items.filter(filter) : items).slice(0, limit);
  if (shown.length === 0) return emptyText ? <p className="text-muted-foreground text-sm">{emptyText}</p> : null;

  return (
    <ul className="space-y-2" aria-label="Nudges">
      {shown.map((n) => {
        const Icon = ICON[n.severity];
        return (
          <li key={n.id} className={cn("flex items-start gap-3 rounded-lg border p-3", TONE[n.severity])}>
            <Icon className={cn("mt-0.5 size-4 shrink-0", n.severity === "critical" && "text-destructive", n.severity === "warning" && "text-warning", n.severity === "good" && "text-success")} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{n.title}</p>
              <p className="text-muted-foreground text-sm">{n.message}</p>
              {n.link && (
                <Link href={n.link} className="text-primary text-sm font-medium hover:underline">
                  Take a look
                </Link>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={`Dismiss: ${n.title}`}
              onClick={async () => {
                setItems((xs) => xs && xs.filter((x) => x.id !== n.id));
                await api(`/nudges/${n.id}/dismiss`, {});
              }}
            >
              <XIcon className="size-4" />
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
