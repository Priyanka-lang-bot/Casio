"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRightIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { api, type User } from "@/lib/api";

// "Try CASIO Demo": creates a private sandbox full of fictional sample data
// and signs this browser into it. No sign-up and no password.
export function DemoButton() {
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

  return (
    <div className="space-y-2">
      <button type="button" className="demo-cta" onClick={start} disabled={busy} aria-describedby="demo-note">
        <span className="demo-cta-cards" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-base font-bold tracking-tight">{busy ? "Preparing your demo…" : "Try CASIO Demo"}</span>
          <span className="block text-xs text-white/80">No sign-up. Opens a fully populated sample account.</span>
        </span>
        <ArrowRightIcon className="size-5 shrink-0" aria-hidden="true" />
      </button>
      <p id="demo-note" className="text-muted-foreground text-xs leading-relaxed">
        You get your own private sandbox with six months of fictional data (in ₹). Nothing you change affects anyone else, and it&apos;s deleted after 24 hours.
      </p>
      {error && <Alert kind="error">{error}</Alert>}
    </div>
  );
}
