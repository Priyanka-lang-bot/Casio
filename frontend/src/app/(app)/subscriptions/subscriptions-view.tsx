"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  BellIcon,
  CalendarClockIcon,
  ChevronDownIcon,
  SparklesIcon,
  TrendingDownIcon,
  TrendingUpIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react";
import { BasisBadge } from "@/components/basis-badge";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { FREQUENCY_LABELS, formatDate, formatMoney } from "@/lib/format";
import type { Recurring, RecurringAlert, RecurringPage } from "@/lib/types";
import { cn } from "@/lib/utils";

type Patch = Partial<Pick<Recurring, "name" | "kind" | "status" | "usage">>;

const KIND_LABEL = { subscription: "Subscription", bill: "Bill", other: "Regular payment" } as const;
const USAGE = [
  ["using", "I use it"],
  ["rarely", "Rarely"],
  ["not_using", "Not using"],
] as const;

export function SubscriptionsView() {
  const [data, setData] = useState<RecurringPage | null>(null);
  const [error, setError] = useState("");
  const [showHidden, setShowHidden] = useState(false);

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);
  useEffect(() => {
    api<RecurringPage>("/subscriptions").then((r) => (r.ok ? setData(r.data) : setError(r.message)));
  }, [version]);

  async function patch(item: Recurring, body: Patch) {
    const r = await api<Recurring>(`/subscriptions/${item.id}`, body, "PATCH");
    if (!r.ok) return setError(r.message);
    setError("");
    load();
  }

  async function dismiss(alert: RecurringAlert) {
    setData((d) => d && { ...d, alerts: d.alerts.filter((a) => a.id !== alert.id) });
    await api(`/subscriptions/alerts/${alert.id}/dismiss`, {});
  }

  if (error && !data) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-muted-foreground py-10 text-center text-sm">Looking for repeating payments…</p>;

  const c = data.currency;
  const s = data.summary;
  const live = data.items.filter((i) => i.status === "active");
  const hidden = data.items.filter((i) => i.status !== "active");
  const byId = Object.fromEntries(data.items.map((i) => [i.id, i]));
  const groups = [
    { kind: "subscription", title: "Subscriptions", hint: "Services you pay for on a schedule." },
    { kind: "bill", title: "Bills", hint: "Rent, utilities and other regular bills. The amount can change." },
    { kind: "other", title: "Other regular payments", hint: "Payments to the same place at regular times, like savings plans or deliveries." },
  ] as const;

  return (
    <>
      <PageHeader
        title="Subscriptions"
        description={`Payments CASIO saw repeating every week, month, quarter or year. Based on your transactions up to ${formatDate(data.as_of)}.`}
      />
      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}

      {data.items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <CalendarClockIcon className="text-muted-foreground size-10" />
            <p className="font-medium">No repeating payments found yet</p>
            <p className="text-muted-foreground max-w-md text-sm">
              CASIO needs a few months of transactions to spot a pattern (at least 2 to 3 payments to the same place). Import a longer
              statement, or try the <a href="/samples/sample-6-months.csv" download className="underline">6-month sample</a> on the{" "}
              <Link href="/import" className="underline">Import</Link> page.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Regular payments per month" value={formatMoney(s.monthly_total, c)} sub={`${s.active_count} active`} />
            <Stat label="Per year" value={formatMoney(s.yearly_total, c)} sub="if nothing changes" />
            <Stat label="Subscriptions per month" value={formatMoney(s.subscriptions_monthly, c)} sub={`Bills: ${formatMoney(s.bills_monthly, c)}`} />
            <Stat
              label="You could save per year"
              value={formatMoney(s.not_using_yearly, c)}
              sub={Number(s.not_using_yearly) > 0 ? "on services you said you don't use" : s.unknown_usage_count ? `Tell us which of ${s.unknown_usage_count} you use` : "Nothing marked unused"}
              tone={Number(s.not_using_yearly) > 0 ? "good" : undefined}
            />
          </div>

          {data.alerts.length > 0 && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><BellIcon className="size-4" /> Things to check ({data.alerts.length})</CardTitle>
                <CardDescription>CASIO noticed these changes in your regular payments.</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {data.alerts.map((a) => (
                    <AlertRow key={a.id} alert={a} item={byId[a.recurring_payment_id]} onPatch={patch} onDismiss={() => dismiss(a)} />
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {groups.map((g) => {
            const items = live.filter((i) => i.kind === g.kind);
            if (!items.length) return null;
            return (
              <section key={g.kind} className="mb-6">
                <h2 className="text-lg font-semibold">{g.title}</h2>
                <p className="text-muted-foreground mb-3 text-sm">{g.hint}</p>
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  {items.map((i) => (
                    <PaymentCard key={i.id} item={i} currency={c} onPatch={(b) => patch(i, b)} />
                  ))}
                </div>
              </section>
            );
          })}

          {hidden.length > 0 && (
            <section className="mb-6">
              <button className="flex items-center gap-1 text-sm font-medium" onClick={() => setShowHidden((v) => !v)} aria-expanded={showHidden}>
                Cancelled and hidden ({hidden.length})
                <ChevronDownIcon className={cn("size-4 transition-transform", showHidden && "rotate-180")} />
              </button>
              {showHidden && (
                <ul className="mt-3 divide-y rounded-lg border bg-white">
                  {hidden.map((i) => (
                    <li key={i.id} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm">
                      <span className="flex-1 font-medium">{i.name}</span>
                      <Badge variant="outline">{i.status === "cancelled" ? "You cancelled it" : "Not a regular payment"}</Badge>
                      <span className="text-muted-foreground">{formatMoney(i.amount, c)} · {FREQUENCY_LABELS[i.frequency].toLowerCase()}</span>
                      <Button size="sm" variant="ghost" onClick={() => patch(i, { status: "active" })}>Show again</Button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <p className="text-muted-foreground text-center text-xs">
            CASIO finds these from your bank transactions. It can&apos;t see whether you actually use a service, so it asks you. Next
            payment dates are forecasts, not promises.
          </p>
        </>
      )}
    </>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" }) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <p className="text-muted-foreground flex items-center justify-between gap-2 text-sm">{label}</p>
        <p className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "good" && "text-success")}>{value}</p>
        {sub && <p className="text-muted-foreground mt-1 text-xs">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function AlertRow({
  alert,
  item,
  onPatch,
  onDismiss,
}: {
  alert: RecurringAlert;
  item: Recurring | undefined;
  onPatch: (item: Recurring, body: Patch) => void;
  onDismiss: () => void;
}) {
  const Icon =
    alert.kind === "price_increase" || alert.kind === "unusual_amount"
      ? TrendingUpIcon
      : alert.kind === "price_decrease"
        ? TrendingDownIcon
        : alert.kind === "new"
          ? SparklesIcon
          : alert.kind === "usage_check"
            ? BellIcon
            : TriangleAlertIcon;
  const tone = alert.kind === "price_decrease" || alert.kind === "new" || alert.kind === "usage_check" ? "text-primary" : "text-warning";
  return (
    <li className="flex flex-wrap items-start gap-3 py-3">
      <Icon className={cn("mt-0.5 size-4 shrink-0", tone)} />
      <p className="min-w-0 flex-1 text-sm">{alert.message}</p>
      <div className="flex flex-wrap gap-1">
        {item && alert.kind === "usage_check" &&
          USAGE.map(([value, label]) => (
            <Button key={value} size="sm" variant="outline" onClick={() => onPatch(item, { usage: value })}>{label}</Button>
          ))}
        {item && alert.kind === "missed" && (
          <Button size="sm" variant="outline" onClick={() => onPatch(item, { status: "cancelled" })}>I cancelled it</Button>
        )}
        {item && alert.kind === "new" && (
          <Button size="sm" variant="outline" onClick={() => onPatch(item, { status: "not_recurring" })}>Not a subscription</Button>
        )}
        <Button size="sm" variant="ghost" onClick={onDismiss} aria-label="Dismiss">
          {alert.kind === "usage_check" ? "Later" : <><XIcon /> Got it</>}
        </Button>
      </div>
    </li>
  );
}

function PaymentCard({ item: i, currency: c, onPatch }: { item: Recurring; currency: string; onPatch: (b: Patch) => void }) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(i.name);
  const lastChange = i.price_changes.at(-1);
  const max = Math.max(...i.charges.map((x) => Number(x.amount)), 1);

  return (
    <Card className="gap-3 py-4">
      <CardContent className="space-y-3 px-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            {renaming ? (
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (name.trim()) onPatch({ name: name.trim() });
                  setRenaming(false);
                }}
              >
                <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" maxLength={100} autoFocus />
                <Button size="sm" type="submit">Save</Button>
              </form>
            ) : (
              <button className="text-left font-semibold hover:underline" onClick={() => setRenaming(true)} title="Rename">{i.name}</button>
            )}
            <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-1.5 text-xs">
              <Badge variant="secondary">{KIND_LABEL[i.kind]}</Badge>
              {i.category_name && <span>{i.category_name}</span>}
              {i.state === "overdue" && <Badge variant="warning">Payment not seen</Badge>}
              {i.usage === "not_using" && <Badge variant="warning">You don&apos;t use it</Badge>}
              {i.usage === "rarely" && <Badge variant="outline">Used rarely</Badge>}
              {i.usage === "using" && <Badge variant="success">You use it</Badge>}
            </div>
          </div>
          <div className="text-right">
            <p className="font-semibold tabular-nums">{i.amount_varies ? "~" : ""}{formatMoney(i.amount_varies ? i.average_amount : i.amount, c)}</p>
            <p className="text-muted-foreground text-xs">{FREQUENCY_LABELS[i.frequency]}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {i.next_expected_on && (
            <span className="flex items-center gap-1.5">
              <CalendarClockIcon className="text-muted-foreground size-4" />
              {i.state === "overdue" ? "Was due" : "Next"} around {formatDate(i.next_expected_on)} <BasisBadge basis="forecast" />
            </span>
          )}
          <span className="text-muted-foreground text-xs">{formatMoney(i.yearly_cost, c)} a year</span>
        </div>

        {lastChange && (
          <p className={cn("flex items-center gap-1.5 text-sm", Number(lastChange.new) > Number(lastChange.old) ? "text-warning" : "text-success")}>
            {Number(lastChange.new) > Number(lastChange.old) ? <TrendingUpIcon className="size-4" /> : <TrendingDownIcon className="size-4" />}
            Price changed from {formatMoney(lastChange.old, c)} to {formatMoney(lastChange.new, c)} on {formatDate(lastChange.date)}
          </p>
        )}

        {i.kind === "subscription" && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-muted-foreground mr-1 text-xs">Do you use it?</span>
            {USAGE.map(([value, label]) => (
              <Button
                key={value}
                size="sm"
                variant={i.usage === value ? "default" : "outline"}
                className="h-7 px-2.5 text-xs"
                aria-pressed={i.usage === value}
                onClick={() => onPatch({ usage: i.usage === value ? "unknown" : value })}
              >
                {label}
              </Button>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t pt-2">
          <button className="text-primary flex items-center gap-1 text-xs font-medium" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            Why CASIO thinks this repeats
            <ChevronDownIcon className={cn("size-3.5 transition-transform", open && "rotate-180")} />
          </button>
          <div className="ml-auto flex gap-1">
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => onPatch({ status: "cancelled" })}>I cancelled it</Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => onPatch({ status: "not_recurring" })}>Not regular</Button>
          </div>
        </div>
        {open && (
          <div className="space-y-2 text-xs">
            <p className="text-muted-foreground">{i.explanation} {Math.round(i.confidence * 100)}% sure.</p>
            <div className="flex h-16 items-end gap-1" aria-label="Payment history">
              {i.charges.map((ch) => (
                <div key={ch.date} className="flex flex-1 flex-col items-center gap-1" title={`${formatDate(ch.date)}: ${formatMoney(ch.amount, c)}`}>
                  <div className="bg-primary/70 w-full max-w-6 rounded-t" style={{ height: `${Math.max(8, (Number(ch.amount) / max) * 48)}px` }} />
                </div>
              ))}
            </div>
            <ul className="text-muted-foreground grid grid-cols-2 gap-x-4 sm:grid-cols-3">
              {i.charges.slice(-6).map((ch) => (
                <li key={ch.date}>{formatDate(ch.date)}: {formatMoney(ch.amount, c)}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
