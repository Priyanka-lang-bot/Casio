"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { ArrowRightIcon, EyeIcon, LockKeyholeIcon, ShieldCheckIcon, SparklesIcon } from "lucide-react";
import { CardFace } from "@/components/wallet/card-face";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import { NAV, type NavItem } from "@/lib/nav";
import type { Overview } from "@/lib/types";
import { cn } from "@/lib/utils";

const POCKETS: { id: NavItem["group"]; title: string; subtitle: string }[] = [
  { id: "everyday", title: "Everyday money", subtitle: "Track, import and understand" },
  { id: "plan", title: "Plan & grow", subtitle: "Profile, goals and guidance" },
];

// Problems people have with finance apps, and where CASIO answers each one.
const HELPS: { problem: string; answer: string; href: string }[] = [
  { problem: "Confusing navigation", answer: "Every feature is a card. Pick one; the back button brings you here.", href: "/wallet" },
  { problem: "Financial jargon", answer: "Plain words: money in, money out, what's left. Short explanations next to the numbers.", href: "/overview" },
  { problem: "Numbers you can't check", answer: "Each figure is labelled actual, your estimate or forecast, with how it was worked out.", href: "/money-model" },
  { problem: "Wrong categories", answer: "Fix a category and choose whether CASIO should remember it as a rule.", href: "/rules" },
  { problem: "One size fits all", answer: "Your profile, rules, budgets and goals shape every total and answer.", href: "/profile" },
  { problem: "Hidden recurring payments", answer: "Subscriptions and price rises are found from your statements.", href: "/subscriptions" },
  { problem: "Hard to get started", answer: "Import a statement in one step, or explore the demo first.", href: "/import" },
  { problem: "No view of the future", answer: "Goals, budgets and what-if scenarios use the same tested calculations.", href: "/what-if" },
  { problem: "Privacy worries", answer: "Your data is visible only to your account. Download or delete it any time.", href: "/settings" },
];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

export function WalletView({ firstName, isDemo }: { firstName: string; isDemo: boolean }) {
  const router = useRouter();
  const reduced = usePrefersReducedMotion();
  const stageRef = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  const [active, setActive] = useState<NavItem>(NAV[0]);
  const [opening, setOpening] = useState<string | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);

  useEffect(() => {
    api<Overview>("/overview").then((r) => r.ok && setOv(r.data));
  }, []);

  // Gentle tilt that follows the pointer (desktop only, off for reduced motion).
  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (reduced || e.pointerType !== "mouse" || !stageRef.current) return;
      const el = stageRef.current;
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(() => {
        el.style.setProperty("--tilt-y", `${(x * 9).toFixed(2)}deg`);
        el.style.setProperty("--tilt-x", `${(-y * 6).toFixed(2)}deg`);
      });
    },
    [reduced],
  );
  const onPointerLeave = () => {
    stageRef.current?.style.setProperty("--tilt-y", "0deg");
    stageRef.current?.style.setProperty("--tilt-x", "0deg");
  };

  function open(e: React.MouseEvent<HTMLAnchorElement>, item: NavItem) {
    // Let the browser handle new-tab clicks normally.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    if (opening) return;
    setActive(item);
    if (reduced) {
      router.push(item.href);
      return;
    }
    setOpening(item.href);
    window.setTimeout(() => router.push(item.href), 320);
  }

  // Arrow keys move between cards in reading order.
  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
    if (!keys.includes(e.key)) return;
    const links = Array.from(e.currentTarget.querySelectorAll<HTMLAnchorElement>("a[data-card]"));
    const i = links.indexOf(document.activeElement as HTMLAnchorElement);
    if (i === -1) return;
    e.preventDefault();
    const next =
      e.key === "Home" ? 0 : e.key === "End" ? links.length - 1 : e.key === "ArrowRight" || e.key === "ArrowDown" ? (i + 1) % links.length : (i - 1 + links.length) % links.length;
    links[next].focus();
  }

  const c = ov?.currency ?? "INR";
  let order = 0;

  return (
    <div className="wallet-page">
      <section className="wallet-hero" aria-labelledby="wallet-title">
        <div className="wallet-intro">
          <p className="wallet-kicker">
            <SparklesIcon className="size-3.5" aria-hidden="true" /> Personal financial intelligence
          </p>
          <h1 id="wallet-title" className="wallet-title">
            {firstName ? `${firstName}'s money,` : "Your money,"}
            <br />
            <span>in one wallet.</span>
          </h1>
          <p className="wallet-lead">
            Every CASIO feature is a card. Pick one to open it. Your browser&apos;s back button, or the Wallet button, brings you back here.
          </p>

          {ov?.has_transactions && (
            <dl className="wallet-stats" aria-label={`This month, ${formatMonth(ov.month)}`}>
              <div>
                <dt>Money in</dt>
                <dd>{formatMoney(ov.actual.month_income, c)}</dd>
              </div>
              <div>
                <dt>Money out</dt>
                <dd>{formatMoney(ov.actual.month_expenses, c)}</dd>
              </div>
              <div>
                <dt>Left so far</dt>
                <dd className={Number(ov.actual.month_net) >= 0 ? "pos" : "neg"}>{formatMoney(ov.actual.month_net, c)}</dd>
              </div>
              <p className="wallet-stats-note">
                {formatMonth(ov.month)} so far, from recorded transactions. Left = money in − money out.
              </p>
            </dl>
          )}

          <div className="wallet-detail" aria-live="polite">
            <p className="wallet-detail-label">
              <span className="wallet-swatch" style={{ background: `linear-gradient(135deg, ${active.theme.from}, ${active.theme.to})` }} />
              {active.label}
            </p>
            <p className="wallet-detail-desc">{active.description}</p>
            <Link href={active.href} className="wallet-open" onClick={(e) => open(e, active)}>
              Open {active.short} <ArrowRightIcon className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </div>

        <div
          ref={stageRef}
          className={cn("wallet-stage", opening && "is-opening", reduced && "reduce-motion")}
          onPointerMove={onPointerMove}
          onPointerLeave={onPointerLeave}
          onKeyDown={onKeyDown}
        >
          <nav aria-label="CASIO features" className="wallet-3d">
            {POCKETS.map((p, pi) => {
              const items = NAV.filter((n) => n.group === p.id);
              return (
                <div key={p.id} className={cn("pocket", pi === 0 ? "pocket-left" : "pocket-right")}>
                  <h2 className="sr-only">{p.title}</h2>
                  <ul className="pocket-cards" style={{ "--n": items.length } as CSSProperties}>
                    {items.map((item, idx) => {
                      const depth = items.length - 1 - idx; // first item sits at the back, highest
                      const o = order++;
                      const navIndex = NAV.indexOf(item);
                      return (
                        <li key={item.href} className="pocket-slot" style={{ "--d": depth, "--o": o, zIndex: 10 + (items.length - depth) } as CSSProperties}>
                          <Link
                            href={item.href}
                            data-card
                            className={cn("wallet-card", opening === item.href && "is-open", active.href === item.href && "is-active")}
                            onClick={(e) => open(e, item)}
                            onMouseEnter={() => setActive(item)}
                            onFocus={() => setActive(item)}
                            aria-label={`${item.label}: ${item.description}`}
                          >
                            <CardFace item={item} index={navIndex} />
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                  <div className="pocket-front" aria-hidden="true">
                    <span className="pocket-band" />
                    <span className="pocket-title">{p.title}</span>
                    <span className="pocket-sub">{p.subtitle}</span>
                    {pi === 0 ? <span className="pocket-badge">C</span> : <span className="pocket-badge pocket-badge-alt">₹</span>}
                  </div>
                </div>
              );
            })}
          </nav>
          <div className="wallet-shadow" aria-hidden="true" />
          <span className="wallet-coin coin-a" aria-hidden="true">₹</span>
          <span className="wallet-coin coin-b" aria-hidden="true" />
          <span className="wallet-coin coin-c" aria-hidden="true" />
          <p className="wallet-hint">
            <kbd>Tab</kbd> or arrow keys to move between cards, <kbd>Enter</kbd> to open
          </p>
        </div>
      </section>

      <section className="wallet-helps" aria-labelledby="helps-title">
        <h2 id="helps-title">What CASIO does differently</h2>
        <ul>
          {HELPS.map((h) => (
            <li key={h.problem}>
              <Link href={h.href}>
                <span className="helps-problem">{h.problem}</span>
                <span className="helps-answer">{h.answer}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="wallet-privacy" aria-labelledby="privacy-title">
        <h2 id="privacy-title">
          <ShieldCheckIcon className="size-5" aria-hidden="true" /> How your data is handled
        </h2>
        <ul>
          <li>
            <LockKeyholeIcon aria-hidden="true" /> Only your account can see your transactions, rules and goals. Sign-in uses a secure, HTTP-only session cookie and passwords are stored as Argon2 hashes.
          </li>
          <li>
            <EyeIcon aria-hidden="true" /> Totals, forecasts and what-if results come from CASIO&apos;s own calculations on your data. When the AI coach is switched on, account numbers and UPI IDs are removed from descriptions before anything is sent.
          </li>
          <li>
            <ShieldCheckIcon aria-hidden="true" /> You can download everything CASIO stores or delete your account in Settings.
            {isDemo && " Demo sandboxes hold only fictional data and are deleted automatically after 24 hours."}
          </li>
        </ul>
      </section>
    </div>
  );
}
