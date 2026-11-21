"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { ArrowRightIcon, CheckIcon, FileDownIcon, LockKeyholeIcon, MenuIcon, ShieldCheckIcon, SparklesIcon, TrendingUpIcon } from "lucide-react";
import { DemoButton, DemoPill } from "@/components/demo-button";
import { ThemeToggle } from "@/components/theme-toggle";
import { CardFace } from "@/components/wallet/card-face";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

const inr = (n: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

const HOLDERS = [
  { id: "everyday", title: "Everyday Money", subtitle: "Track, import and understand" },
  { id: "plan", title: "Plan & Grow", subtitle: "Profile, goals and guidance" },
] as const;

const MARQUEE = [
  "Money in",
  "Money out",
  "What's left",
  "Subscriptions, found",
  "Rules you approve",
  "Forecasts you can check",
  "Goals with dates",
  "What-ifs in seconds",
];

// Sample rows from the demo account's statement (fictional).
const IMPORT_ROWS = [
  { date: "02 Nov", desc: "NIMBUS ANALYTICS PVT LTD · Salary", amt: 45000, cat: "Income", status: "new" },
  { date: "03 Nov", desc: "UPI-CHAI POINT-chaipoint@ybl", amt: -140, cat: "Food and Dining", status: "rule" },
  { date: "05 Nov", desc: "NETFLIX.COM", amt: -649, cat: "Entertainment", status: "new" },
  { date: "05 Nov", desc: "UPI-BLUE PEAK ROASTERS", amt: -260, cat: "Other", status: "check" },
  { date: "28 Oct", desc: "SWIGGY ORDER 8812", amt: -386, cat: "Food and Dining", status: "dup" },
];
const STATUS = {
  new: { text: "New", cls: "is-new" },
  rule: { text: "Your rule", cls: "is-rule" },
  check: { text: "Check category", cls: "is-check" },
  dup: { text: "Already imported", cls: "is-dup" },
} as const;

const SUBS = [
  { name: "Netflix", amt: 649, was: 499, every: "monthly" },
  { name: "Cult.fit membership", amt: 999, every: "monthly" },
  { name: "YouTube Premium", amt: 129, every: "monthly" },
  { name: "Spotify", amt: 119, every: "monthly" },
];

// A typical month in the demo account, rounded for the illustration.
const MONTHS = [
  { m: "Jun", inc: 45000, out: 27900 },
  { m: "Jul", inc: 45000, out: 29100 },
  { m: "Aug", inc: 45000, out: 28200 },
  { m: "Sep", inc: 45000, out: 28600 },
  { m: "Oct", inc: 45000, out: 28480 },
  { m: "Nov", inc: 45000, out: 31700 },
];
const CATS = [
  { name: "Rent", amt: 10000 },
  { name: "Food and Dining", amt: 6200 },
  { name: "Shopping", amt: 3400 },
  { name: "Bills and Utilities", amt: 2950 },
  { name: "Transport", amt: 1900 },
];

function useReveal() {
  useEffect(() => {
    const root = document.documentElement;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    root.classList.add("js-reveal");
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        }),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
    return () => {
      io.disconnect();
      root.classList.remove("js-reveal");
    };
  }, []);
}

function WalletPreview() {
  let order = 0;
  return (
    <div className="wallet-stage is-preview" aria-hidden="true">
      <div className="wallet-book leather">
        {HOLDERS.map((h, hi) => {
          const items = NAV.filter((n) => n.group === h.id);
          return (
            <div key={h.id} className="contents">
              {hi === 1 && <div className="wallet-spine" />}
              <div className={cn("wallet-half leather", hi === 0 ? "wallet-half-left" : "wallet-half-right")} style={{ "--n": items.length } as CSSProperties}>
                <ul className="slots">
                  {items.map((item, idx) => (
                    <li key={item.href} className="slot" style={{ "--i": idx, "--o": order++, zIndex: 10 + idx } as CSSProperties}>
                      <div className={cn("wallet-card", item.href === "/subscriptions" && "is-active")}>
                        <CardFace item={item} index={NAV.indexOf(item)} />
                      </div>
                      <span className="slot-lip leather" />
                    </li>
                  ))}
                </ul>
                <div className="front-pocket leather">
                  <span className="pocket-title">{h.title}</span>
                  <span className="pocket-sub">{h.subtitle}</span>
                  <span className="pocket-snap" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="wallet-shadow" />
    </div>
  );
}

function WhatIfPreview() {
  const dining = 3220; // the demo account's usual monthly dining spend, rounded
  const [pct, setPct] = useState(30);
  const monthly = Math.round((dining * pct) / 100);
  return (
    <div className="lp-panel">
      <p className="lp-panel-kicker">What-If Simulator · demo numbers</p>
      <label htmlFor="lp-dining" className="mt-3 block text-sm font-semibold">
        Spend less on dining out: <span className="text-primary tabular-nums">{pct}%</span>
      </label>
      <input id="lp-dining" type="range" min={0} max={60} step={5} value={pct} onChange={(e) => setPct(Number(e.target.value))} className="range mt-2" />
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="lp-figure">
          <span>Each month</span>
          <strong className="tabular-nums">+{inr(monthly)}</strong>
        </div>
        <div className="lp-figure">
          <span>Over 6 months</span>
          <strong className="tabular-nums">+{inr(monthly * 6)}</strong>
        </div>
      </div>
      <div className="lp-bars mt-4" aria-hidden="true">
        {[1, 2, 3, 4, 5, 6].map((m) => (
          <span key={m} style={{ "--h": `${Math.max(4, (monthly * m) / ((dining * 0.6 * 6) / 100))}%` } as CSSProperties} />
        ))}
      </div>
      <p className="text-muted-foreground mt-3 text-xs">Drag the slider. Usual dining spend in the demo is about {inr(dining)} a month; the app works this out from your own transactions.</p>
    </div>
  );
}

export function Landing({ signedIn }: { signedIn: boolean }) {
  useReveal();
  const menuRef = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => menuRef.current?.removeAttribute("open");
  const maxOut = Math.max(...MONTHS.map((m) => m.inc));

  const primaryCta = signedIn ? (
    <Link href="/wallet" className="lp-pill">
      Open your wallet <ArrowRightIcon className="size-4" aria-hidden="true" />
    </Link>
  ) : (
    <DemoPill />
  );

  return (
    <div className="lp paper-bg">
      <a href="#top" className="skip-link">
        Skip to content
      </a>
      <header className="lp-nav">
        <Link href="/" className="app-logo" aria-label="CASIO home">
          <span className="app-logo-mark" aria-hidden="true">C</span>
          CASIO
        </Link>
        <nav aria-label="Sections" className="lp-links">
          <a href="#cards">The cards</a>
          <a href="#import">Import</a>
          <a href="#how">How it works</a>
          <a href="#reports">Reports</a>
          <a href="#privacy">Privacy</a>
        </nav>
        <div className="lp-nav-end">
          <ThemeToggle />
          {!signedIn && (
            <Link href="/login" className="lp-login">
              Log in
            </Link>
          )}
          <span className="hidden sm:inline-flex">{primaryCta}</span>
          <details ref={menuRef} className="lp-menu">
            <summary aria-label="Menu">
              <MenuIcon className="size-5" />
            </summary>
            <div className="lp-menu-panel" onClick={closeMenu}>
              <a href="#cards">The cards</a>
              <a href="#import">Import</a>
              <a href="#how">How it works</a>
              <a href="#reports">Reports</a>
              <a href="#privacy">Privacy</a>
              {signedIn ? <Link href="/wallet">Open your wallet</Link> : <Link href="/register">Create an account</Link>}
            </div>
          </details>
        </div>
      </header>

      <main id="top">
        {/* ---------------------------------------------------------------- Hero */}
        <section className="lp-hero">
          <div className="lp-hero-copy">
            <p className="lp-kicker">
              <span className="lp-dot" aria-hidden="true" /> Personal finance, in fourteen cards
            </p>
            <h1 className="lp-display" aria-label="Your money, neatly folded.">
              {["Your", "money,"].map((w, i) => (
                <span key={w} className="lp-word" style={{ "--w": i } as CSSProperties} aria-hidden="true">
                  {w}
                </span>
              ))}
              <br aria-hidden="true" />
              <em className="lp-word" style={{ "--w": 2 } as CSSProperties} aria-hidden="true">
                neatly
              </em>
              <span className="lp-word" style={{ "--w": 3 } as CSSProperties} aria-hidden="true">
                folded.
              </span>
            </h1>
            <p className="lp-lead">
              CASIO reads your bank statements and files everything into a leather wallet of cards: what came in, what went out, the subscriptions you forgot,
              and where the month is heading. Every number says how it was worked out.
            </p>
            <div className="lp-hero-cta">
              {signedIn ? (
                <Link href="/wallet" className="lp-pill lp-pill-lg">
                  Open your wallet <ArrowRightIcon className="size-5" aria-hidden="true" />
                </Link>
              ) : (
                <div className="w-full max-w-sm">
                  <DemoButton note={false} />
                </div>
              )}
              {!signedIn && (
                <p className="lp-hero-alt">
                  or <Link href="/register">create a free account</Link> · <Link href="/login">log in</Link>
                </p>
              )}
            </div>
            <ul className="lp-hero-facts">
              <li>
                <CheckIcon aria-hidden="true" /> Sample account in ₹ with six months of data
              </li>
              <li>
                <CheckIcon aria-hidden="true" /> Private sandbox, deleted after 24 hours
              </li>
            </ul>
          </div>
          <div className="lp-hero-wallet">
            <WalletPreview />
            <p className="lp-caption">The CASIO wallet. Left holder: everyday money. Right holder: plans and guidance.</p>
          </div>
        </section>

        {/* ------------------------------------------------------------ Marquee */}
        <div className="lp-marquee" aria-hidden="true">
          <div className="lp-marquee-track">
            {[0, 1].map((k) => (
              <span key={k}>
                {MARQUEE.map((m) => (
                  <span key={m}>
                    {m} <span className="lp-star">✦</span>{" "}
                  </span>
                ))}
              </span>
            ))}
          </div>
        </div>

        {/* -------------------------------------------------------------- Cards */}
        <section id="cards" className="lp-section">
          <div className="lp-section-head reveal">
            <p className="lp-eyebrow">01 · The cards</p>
            <h2 className="lp-h2">
              Fourteen cards. <em>One wallet.</em>
            </h2>
            <p className="lp-sub">
              Finance apps hide features behind menus. CASIO puts each one on its own card, numbered and colour-coded. Pick a card, and the back button brings you
              home.
            </p>
          </div>
          <div className="lp-index">
            {HOLDERS.map((h) => (
              <div key={h.id} className="lp-index-col reveal">
                <h3>
                  {h.title} <span>{h.subtitle}</span>
                </h3>
                <ol>
                  {NAV.filter((n) => n.group === h.id).map((n) => (
                    <li key={n.href}>
                      <span className="lp-index-no">{String(NAV.indexOf(n) + 1).padStart(2, "0")}</span>
                      <span className="lp-index-swatch" style={{ background: `linear-gradient(135deg, ${n.theme.from}, ${n.theme.to})` }} aria-hidden="true">
                        <n.icon className={n.theme.ink === "light" ? "text-white" : "text-[#1b1f2a]"} />
                      </span>
                      <span>
                        <strong>{n.label}</strong>
                        <span className="lp-index-desc">{n.description}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </section>

        {/* ------------------------------------------------------------ Spreads */}
        <section id="import" className="lp-spread">
          <div className="lp-spread-copy reveal">
            <p className="lp-eyebrow">02 · Smart import</p>
            <h2 className="lp-h2">
              Drop in a statement. <em>CASIO does the sorting.</em>
            </h2>
            <p className="lp-sub">
              Upload a CSV or PDF statement, or paste bank SMS. CASIO reads each line, suggests a category, applies the rules you approved and flags anything already
              imported. Nothing is saved until you confirm the preview.
            </p>
            <ul className="lp-ticks">
              <li>Duplicate rows are caught and left out</li>
              <li>Your merchant rules are applied and shown</li>
              <li>Unknown merchants are marked for a quick check</li>
            </ul>
          </div>
          <div className="lp-panel reveal">
            <p className="lp-panel-kicker">Import preview · sample statement</p>
            <ul className="lp-rows">
              {IMPORT_ROWS.map((r) => (
                <li key={r.desc} className={cn(r.status === "dup" && "is-muted")}>
                  <span className="lp-row-date">{r.date}</span>
                  <span className="lp-row-desc">
                    {r.desc}
                    <span className="lp-row-cat">{r.cat}</span>
                  </span>
                  <span className={cn("lp-row-amt tabular-nums", r.amt > 0 && "is-in")}>{r.amt > 0 ? `+${inr(r.amt)}` : `−${inr(-r.amt)}`}</span>
                  <span className={cn("lp-badge", STATUS[r.status as keyof typeof STATUS].cls)}>{STATUS[r.status as keyof typeof STATUS].text}</span>
                </li>
              ))}
            </ul>
            <p className="lp-panel-foot">4 to import · 1 duplicate left out</p>
          </div>
        </section>

        <section className="lp-spread is-flipped">
          <div className="lp-spread-copy reveal">
            <p className="lp-eyebrow">03 · Subscriptions</p>
            <h2 className="lp-h2">
              The payments you forgot, <em>found.</em>
            </h2>
            <p className="lp-sub">
              CASIO looks for charges that repeat every week, month or year, totals them, and tells you when a price goes up. Add the ones your bank doesn&apos;t show,
              and see what&apos;s due next.
            </p>
          </div>
          <div className="lp-panel reveal">
            <p className="lp-panel-kicker">Subscriptions · demo account</p>
            <ul className="lp-subs">
              {SUBS.map((s) => (
                <li key={s.name}>
                  <span className="lp-sub-name">{s.name}</span>
                  {s.was && (
                    <span className="lp-badge is-check">
                      <TrendingUpIcon className="size-3" aria-hidden="true" /> was {inr(s.was)}
                    </span>
                  )}
                  <span className="lp-sub-amt tabular-nums">{inr(s.amt)}/mo</span>
                </li>
              ))}
            </ul>
            <div className="lp-panel-total">
              <span>Subscriptions a month</span>
              <strong className="tabular-nums">{inr(SUBS.reduce((a, s) => a + s.amt, 0))}</strong>
            </div>
            <p className="lp-panel-foot">That&apos;s {inr(SUBS.reduce((a, s) => a + s.amt, 0) * 12)} a year.</p>
          </div>
        </section>

        <section className="lp-spread">
          <div className="lp-spread-copy reveal">
            <p className="lp-eyebrow">04 · What-if</p>
            <h2 className="lp-h2">
              Ask &ldquo;what if&rdquo; <em>before you spend.</em>
            </h2>
            <p className="lp-sub">
              Earn more, spend less, save an extra ₹5,000, or plan a big purchase. The simulator recalculates as you move each slider, using the same tested maths as
              your goals and budgets.
            </p>
          </div>
          <div className="reveal">
            <WhatIfPreview />
          </div>
        </section>

        {/* ---------------------------------------------------------- How it works */}
        <section id="how" className="lp-section">
          <div className="lp-section-head reveal">
            <p className="lp-eyebrow">05 · How it works</p>
            <h2 className="lp-h2">
              Three steps, <em>then it&apos;s yours.</em>
            </h2>
          </div>
          <ol className="lp-steps">
            {[
              { t: "Import", d: "Add a bank statement or a few transactions by hand. Or open the demo and explore a ready-made account first." },
              { t: "Correct, once", d: "Fix a category and choose whether CASIO should remember it as a rule. You approve every rule and can undo it." },
              { t: "Plan", d: "Set budgets and goals, try what-ifs and read the monthly report. Forecasts are labelled as forecasts." },
            ].map((s, i) => (
              <li key={s.t} className="reveal" style={{ "--d": i } as CSSProperties}>
                <span className="lp-step-no">0{i + 1}</span>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* -------------------------------------------------------------- Reports */}
        <section id="reports" className="lp-spread is-flipped">
          <div className="lp-spread-copy reveal">
            <p className="lp-eyebrow">06 · Insights &amp; reports</p>
            <h2 className="lp-h2">
              A monthly report <em>you&apos;ll actually read.</em>
            </h2>
            <p className="lp-sub">
              Money in, money out, what&apos;s left, top categories and what changed since last month, in plain words. Spot unusual one-off payments and download the
              report as a spreadsheet.
            </p>
            <ul className="lp-ticks">
              <li>Actual, estimate and forecast labels on every figure</li>
              <li>Unusual spending flagged with the reason</li>
              <li>Download as CSV or print</li>
            </ul>
          </div>
          <div className="lp-panel lp-report reveal">
            <div className="flex items-baseline justify-between gap-3">
              <p className="lp-panel-kicker">Monthly report · typical demo month</p>
              <FileDownIcon className="text-muted-foreground size-4" aria-hidden="true" />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <div className="lp-figure">
                <span>Money in</span>
                <strong className="tabular-nums">{inr(45000)}</strong>
              </div>
              <div className="lp-figure">
                <span>Money out</span>
                <strong className="tabular-nums">{inr(28480)}</strong>
              </div>
              <div className="lp-figure">
                <span>Left</span>
                <strong className="text-success tabular-nums">{inr(16520)}</strong>
              </div>
            </div>
            <div className="lp-chart" role="img" aria-label="Six months of money in and money out, sample data">
              {MONTHS.map((m, i) => (
                <div key={m.m} className="lp-chart-col">
                  <div className="lp-chart-bars">
                    <span className="is-in" style={{ "--h": `${(m.inc / maxOut) * 100}%`, "--d": i } as CSSProperties} />
                    <span className="is-out" style={{ "--h": `${(m.out / maxOut) * 100}%`, "--d": i } as CSSProperties} />
                  </div>
                  <span className="lp-chart-label">{m.m}</span>
                </div>
              ))}
            </div>
            <ul className="lp-cats">
              {CATS.map((c, i) => (
                <li key={c.name}>
                  <span>{c.name}</span>
                  <span className="lp-cat-track">
                    <span style={{ "--w": `${(c.amt / CATS[0].amt) * 100}%`, "--d": i } as CSSProperties} />
                  </span>
                  <span className="tabular-nums">{inr(c.amt)}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* -------------------------------------------------------------- Privacy */}
        <section id="privacy" className="lp-section">
          <div className="lp-section-head reveal">
            <p className="lp-eyebrow">07 · Privacy</p>
            <h2 className="lp-h2">
              Your data, <em>kept in your pocket.</em>
            </h2>
          </div>
          <div className="lp-privacy">
            <div className="reveal">
              <LockKeyholeIcon aria-hidden="true" />
              <h3>Only you can see it</h3>
              <p>Transactions, rules and goals belong to your account alone. Sessions use a secure cookie and passwords are stored as Argon2 hashes.</p>
            </div>
            <div className="reveal">
              <SparklesIcon aria-hidden="true" />
              <h3>Honest about the coach</h3>
              <p>The finance coach works out answers from your data. When no AI service is connected, a built-in rule-based helper answers and says so.</p>
            </div>
            <div className="reveal">
              <ShieldCheckIcon aria-hidden="true" />
              <h3>Leave any time</h3>
              <p>Download everything CASIO stores, or delete your account, from Settings. Demo sandboxes are deleted automatically.</p>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------- Final CTA */}
        <section className="lp-final">
          <h2 className="lp-final-title reveal">
            Open the <em>wallet.</em>
          </h2>
          <p className="lp-sub mx-auto reveal">See all fourteen cards with a fully populated sample account. No sign-up needed.</p>
          <div className="lp-final-cta reveal">
            {signedIn ? (
              <Link href="/wallet" className="lp-pill lp-pill-lg">
                Open your wallet <ArrowRightIcon className="size-5" aria-hidden="true" />
              </Link>
            ) : (
              <div className="w-full max-w-sm">
                <DemoButton />
              </div>
            )}
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-footer-grid">
          <div>
            <p className="app-logo">
              <span className="app-logo-mark" aria-hidden="true">C</span> CASIO
            </p>
            <p className="lp-footer-note">Personal financial intelligence, in one wallet.</p>
          </div>
          <nav aria-label="Product">
            <p>Product</p>
            <a href="#cards">The cards</a>
            <a href="#how">How it works</a>
            <a href="#reports">Reports</a>
          </nav>
          <nav aria-label="Account">
            <p>Account</p>
            {signedIn ? <Link href="/wallet">Open your wallet</Link> : <Link href="/login">Log in</Link>}
            {!signedIn && <Link href="/register">Create an account</Link>}
          </nav>
        </div>
        <p className="lp-footer-small">
          © 2026 CASIO. Demo data is fictional. CASIO gives general information from your own data, not regulated financial advice.
        </p>
      </footer>
    </div>
  );
}
