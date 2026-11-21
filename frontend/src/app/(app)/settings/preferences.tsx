"use client";

import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { MonitorIcon, MoonIcon, RotateCcwIcon, SunIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { setPref, usePrefs, type Prefs } from "@/lib/prefs";
import { applyTheme, readTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

const subscribe = (cb: () => void) => {
  window.addEventListener("casio-theme", cb);
  return () => window.removeEventListener("casio-theme", cb);
};

function Toggle({ id, label, hint, k, prefs }: { id: string; label: string; hint: string; k: keyof Prefs; prefs: Prefs }) {
  return (
    <div className="flex items-start gap-3">
      <Checkbox id={id} checked={prefs[k]} onCheckedChange={(v) => setPref(k, v === true)} className="mt-0.5" />
      <div>
        <Label htmlFor={id}>{label}</Label>
        <p className="text-muted-foreground mt-0.5 text-xs">{hint}</p>
      </div>
    </div>
  );
}

export function Preferences({ isDemo }: { isDemo: boolean }) {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "system" as ThemeChoice);
  const prefs = usePrefs();
  const router = useRouter();
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState("");

  const THEMES: { v: ThemeChoice; label: string; icon: typeof SunIcon }[] = [
    { v: "light", label: "Light", icon: SunIcon },
    { v: "dark", label: "Dark", icon: MoonIcon },
    { v: "system", label: "Match device", icon: MonitorIcon },
  ];

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Light is ivory paper with cognac leather; dark is charcoal with espresso leather. Saved on this device.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-2">
            {THEMES.map((t) => (
              <button
                key={t.v}
                type="button"
                role="radio"
                aria-checked={theme === t.v}
                onClick={() => applyTheme(t.v)}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-lg border p-3 text-sm font-medium transition-colors",
                  theme === t.v ? "border-primary bg-primary/10" : "hover:bg-accent",
                )}
              >
                <t.icon className="size-5" aria-hidden="true" />
                {t.label}
              </button>
            ))}
          </div>
          <Toggle id="p-motion" k="reduceMotion" prefs={prefs} label="Reduce motion" hint="Turns off card animations, tilting and scrolling effects." />
          <Toggle id="p-hide" k="hideAmounts" prefs={prefs} label="Hide amounts on the wallet" hint="Blurs this month's totals on the home screen, for when someone is looking over your shoulder." />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reminders</CardTitle>
          <CardDescription>
            Choose what CASIO points out inside the app. Saved on this device. CASIO doesn&apos;t send emails or phone notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Toggle id="p-upcoming" k="remindUpcoming" prefs={prefs} label="Upcoming payments" hint="Show regular payments due in the next 30 days on the Subscriptions card." />
          <Toggle id="p-unusual" k="showUnusual" prefs={prefs} label="Unusual spending" hint="Show big one-off payments on the Insights card." />
        </CardContent>
      </Card>

      {isDemo && (
        <Card>
          <CardHeader>
            <CardTitle>Demo data</CardTitle>
            <CardDescription>Start the sample account again from scratch. Everything you changed in this sandbox is replaced with fresh fictional data.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              disabled={resetting}
              onClick={async () => {
                setResetting(true);
                setResetError("");
                const r = await api("/demo/reset", {});
                if (r.ok) {
                  router.replace("/wallet");
                  router.refresh();
                } else {
                  setResetting(false);
                  setResetError(r.message);
                }
              }}
            >
              <RotateCcwIcon /> {resetting ? "Resetting…" : "Reset demo data"}
            </Button>
            {resetError && <div className="mt-3"><Alert kind="error">{resetError}</Alert></div>}
          </CardContent>
        </Card>
      )}
    </>
  );
}
