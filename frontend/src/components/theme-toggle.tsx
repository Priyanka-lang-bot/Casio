"use client";

import { useSyncExternalStore } from "react";
import { MoonIcon, SunIcon } from "lucide-react";
import { applyTheme, isDark, readTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

function subscribe(onChange: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  window.addEventListener("casio-theme", onChange);
  mq.addEventListener("change", onChange);
  return () => {
    window.removeEventListener("casio-theme", onChange);
    mq.removeEventListener("change", onChange);
  };
}

export function useDarkTheme(): boolean {
  return useSyncExternalStore(subscribe, () => isDark(readTheme()), () => false);
}

// One button: switches between the light (ivory) and dark (charcoal) themes.
// The choice is remembered in this browser.
export function ThemeToggle({ className }: { className?: string }) {
  const dark = useDarkTheme();
  const label = dark ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button
      type="button"
      className={cn("theme-toggle", dark && "is-dark", className)}
      aria-label={label}
      title={label}
      onClick={() => applyTheme(dark ? "light" : "dark")}
    >
      <span className="theme-toggle-knob" aria-hidden="true">
        {dark ? <MoonIcon className="size-3.5" /> : <SunIcon className="size-3.5" />}
      </span>
    </button>
  );
}
