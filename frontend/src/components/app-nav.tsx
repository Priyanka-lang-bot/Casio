"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { ChevronLeftIcon, FlaskConicalIcon, LayoutGridIcon, LogOutIcon, RotateCcwIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { NAV, findNav } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

function DemoBanner() {
  const router = useRouter();
  const [busy, setBusy] = useState<"" | "reset" | "exit">("");
  async function reset() {
    setBusy("reset");
    const r = await api("/demo/reset", {});
    if (r.ok) {
      router.replace("/wallet");
      router.refresh();
    }
    setBusy("");
  }
  async function exit() {
    setBusy("exit");
    await api("/auth/logout", {});
    router.replace("/login");
    router.refresh();
  }
  return (
    <div className="demo-banner" role="note" aria-label="Demo mode">
      <span className="demo-pill">
        <FlaskConicalIcon className="size-3.5" aria-hidden="true" /> DEMO · SAMPLE DATA
      </span>
      <span className="demo-text">
        Aanya Kapoor is a fictional person and every amount is sample data. Your changes stay in your own private sandbox, deleted after 24 hours.
      </span>
      <span className="demo-actions">
        <button type="button" onClick={reset} disabled={!!busy}>
          <RotateCcwIcon className="size-3.5" aria-hidden="true" /> {busy === "reset" ? "Resetting…" : "Reset demo"}
        </button>
        <button type="button" onClick={exit} disabled={!!busy}>
          <LogOutIcon className="size-3.5" aria-hidden="true" /> {busy === "exit" ? "Leaving…" : "Exit demo"}
        </button>
      </span>
    </div>
  );
}

// "All cards": a quick switcher so any feature is one click away from any page.
function CardSwitcher({ current }: { current?: string }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node) && !buttonRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  return (
    <div className="relative">
      <Button ref={buttonRef} variant="outline" size="sm" aria-expanded={open} aria-controls="card-switcher" onClick={() => setOpen((o) => !o)}>
        <LayoutGridIcon /> <span className="hidden sm:inline">All cards</span>
      </Button>
      {open && (
        <div ref={panelRef} id="card-switcher" className="switcher-panel" role="dialog" aria-label="All CASIO cards">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold">All cards</p>
            <Button variant="ghost" size="icon" className="size-7" aria-label="Close" onClick={() => setOpen(false)}>
              <XIcon className="size-4" />
            </Button>
          </div>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link
                  href={n.href}
                  aria-current={current === n.href ? "page" : undefined}
                  onClick={() => setOpen(false)}
                  className={cn("mini-card", n.theme.ink === "light" ? "ink-light" : "ink-dark")}
                  style={{ "--c-from": n.theme.from, "--c-to": n.theme.to } as CSSProperties}
                >
                  <n.icon className="size-4" aria-hidden="true" />
                  <span>{n.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UserMenu({ userName, email }: { userName: string; email: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <details className="user-menu">
      <summary aria-label="Account menu">
        <span className="user-avatar" aria-hidden="true">{userName.slice(0, 1).toUpperCase()}</span>
        <span className="hidden max-w-32 truncate text-sm font-medium md:inline">{userName}</span>
      </summary>
      <div className="user-menu-panel">
        <p className="truncate text-sm font-medium">{userName}</p>
        <p className="text-muted-foreground mb-3 truncate text-xs">{email}</p>
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await api("/auth/logout", {});
            router.replace("/login");
            router.refresh();
          }}
        >
          <LogOutIcon /> {busy ? "Logging out…" : "Log out"}
        </Button>
      </div>
    </details>
  );
}

// The frame around every signed-in page. The wallet (/wallet) is the home
// screen; every other page shows a slim top bar with a way back to it.
export function AppShell({ userName, email, isDemo, children }: { userName: string; email: string; isDemo: boolean; children: ReactNode }) {
  const pathname = usePathname();
  const isWallet = pathname === "/wallet";
  const current = findNav(pathname);

  return (
    <div className={cn("flex flex-1 flex-col", isWallet ? "wallet-bg" : "paper-bg")}>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {isDemo && <DemoBanner />}
      <header className={cn("app-bar", isWallet && "app-bar-wallet")}>
        <div className="flex min-w-0 items-center gap-2">
          {!isWallet && (
            <Button asChild variant="ghost" size="sm" className="-ml-2">
              <Link href="/wallet" aria-label="Back to wallet">
                <ChevronLeftIcon /> <span className="hidden sm:inline">Wallet</span>
              </Link>
            </Button>
          )}
          <Link href="/wallet" className="app-logo" aria-label="CASIO wallet home">
            <span className="app-logo-mark" aria-hidden="true">C</span>
            <span className="hidden min-[380px]:inline">CASIO</span>
          </Link>
          {current && (
            <span
              className={cn("current-chip", current.theme.ink === "light" ? "ink-light" : "ink-dark")}
              style={{ "--c-from": current.theme.from, "--c-to": current.theme.to } as CSSProperties}
            >
              <current.icon className="size-3.5" aria-hidden="true" />
              <span className="truncate">{current.short}</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isWallet && <CardSwitcher current={current?.href} />}
          <ThemeToggle />
          <UserMenu userName={userName} email={email} />
        </div>
      </header>
      <main id="main" className={cn("min-w-0 flex-1", !isWallet && "px-4 py-6 sm:px-6 lg:px-10 lg:py-8")}>
        {isWallet ? children : <div className="mx-auto max-w-6xl">{children}</div>}
      </main>
    </div>
  );
}
