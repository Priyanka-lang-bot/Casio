"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRightIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { api, type User } from "@/lib/api";
import { cn } from "@/lib/utils";

function useStartDemo() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    const r = await api<User>("/demo/start", {});
    if (r.ok) {
      router.replace("/wallet");
      router.refresh();
      return;
    }
    setBusy(false);
    setError(r.message);
  }
  return { busy, error, start };
}

// "Try CASIO Demo": creates a private sandbox full of fictional sample data
// and signs this browser into it. No sign-up and no password.
export function DemoButton({ note = true }: { note?: boolean }) {
  const { busy, error, start } = useStartDemo();
  return (
    <div className="space-y-2">
      <button type="button" className="demo-cta" onClick={start} disabled={busy} aria-describedby={note ? "demo-note" : undefined}>
        <span className="demo-cta-cards" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-base font-bold tracking-tight">{busy ? "Preparing your demo…" : "Try CASIO Demo"}</span>
          <span className="block text-xs opacity-80">No sign-up. Opens a fully populated sample account.</span>
        </span>
        <ArrowRightIcon className="size-5 shrink-0" aria-hidden="true" />
      </button>
      {note && (
        <p id="demo-note" className="text-muted-foreground text-xs leading-relaxed">
          You get your own private sandbox with six months of fictional data (in ₹). Nothing you change affects anyone else, and it&apos;s deleted after 24 hours.
        </p>
      )}
      {error && <Alert kind="error">{error}</Alert>}
    </div>
  );
}

// A small pill version for navigation bars.
export function DemoPill({ className, children = "Try the demo" }: { className?: string; children?: React.ReactNode }) {
  const { busy, error, start } = useStartDemo();
  return (
    <>
      <button type="button" className={cn("lp-pill", className)} onClick={start} disabled={busy} title={error || undefined}>
        {busy ? "Opening…" : error ? "Couldn't open. Retry" : children}
        <ArrowRightIcon className="size-4" aria-hidden="true" />
      </button>
      {error && (
        <span role="alert" className="sr-only">
          {error}
        </span>
      )}
    </>
  );
}
