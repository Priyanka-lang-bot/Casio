"use client";

import { useEffect, useRef, useState } from "react";
import { BotIcon, SendIcon, ShieldCheckIcon, Trash2Icon, UserRoundIcon } from "lucide-react";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { CoachMsg } from "@/lib/planning-types";
import { cn } from "@/lib/utils";

const STARTERS = [
  "Where did my money go last month?",
  "How are my budgets doing?",
  "Am I on track for my goals?",
  "Which subscriptions cost me the most?",
  "What if I cut dining by 30%?",
  "How big should my emergency fund be?",
];

const TOOL_LABEL: Record<string, string> = {
  get_money_model: "money model",
  get_month_summary: "monthly totals",
  get_budgets: "budgets",
  get_goals: "goals",
  get_subscriptions: "subscriptions",
  search_transactions: "transactions",
  get_nudges: "alerts",
  run_what_if: "what-if calculator",
};

export function CoachView() {
  const [messages, setMessages] = useState<CoachMsg[] | null>(null);
  const [aiStatus, setAiStatus] = useState<string>("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const tempId = useRef(0);

  useEffect(() => {
    api<{ ai: string; messages: CoachMsg[] }>("/coach").then((r) => {
      if (!r.ok) return setError(r.message);
      setMessages(r.data.messages);
      setAiStatus(r.data.ai);
    });
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setText("");
    setError("");
    setBusy(true);
    const temp: CoachMsg = { id: `tmp-${++tempId.current}`, role: "user", content: question, meta: {}, created_at: "" };
    setMessages((m) => [...(m ?? []), temp]);
    const r = await api<{ question: CoachMsg; answer: CoachMsg }>("/coach", { message: question });
    setBusy(false);
    if (!r.ok) {
      setMessages((m) => (m ?? []).filter((x) => x.id !== temp.id));
      setText(question);
      return setError(r.message);
    }
    setMessages((m) => [...(m ?? []).filter((x) => x.id !== temp.id), r.data.question, r.data.answer]);
  }

  return (
    <>
      <PageHeader
        title="AI Finance Coach"
        description="Ask anything about your money. The coach looks up your real numbers in CASIO before answering."
        action={
          messages && messages.length > 0 ? (
            <Button variant="outline" onClick={async () => { await api("/coach", undefined, "DELETE"); setMessages([]); }}>
              <Trash2Icon /> Clear chat
            </Button>
          ) : undefined
        }
      />
      <div className="text-muted-foreground mb-4 flex flex-wrap items-center gap-2 text-xs">
        <ShieldCheckIcon className="size-4" />
        Guidance on budgeting, saving and planning only. CASIO never recommends specific stocks, funds or crypto.
        {aiStatus === "not_configured" && <Badge variant="secondary">AI is off: built-in helper answers</Badge>}
        {aiStatus === "ready" && <Badge variant="success">AI on</Badge>}
      </div>

      <Card className="flex min-h-[60vh] flex-col py-0">
        <CardContent className="flex flex-1 flex-col gap-4 overflow-y-auto p-4" aria-live="polite">
          {!messages ? (
            <p className="text-muted-foreground m-auto text-sm">Loading…</p>
          ) : messages.length === 0 ? (
            <div className="m-auto max-w-lg space-y-4 text-center">
              <BotIcon className="text-primary mx-auto size-10" />
              <p className="font-medium">Hi! I&apos;m your CASIO coach.</p>
              <p className="text-muted-foreground text-sm">Try one of these:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {STARTERS.map((s) => (
                  <button key={s} type="button" onClick={() => send(s)} className="bg-muted hover:bg-accent rounded-full px-3 py-1.5 text-sm">{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => <Bubble key={m.id} m={m} />)
          )}
          {busy && (
            <div className="text-muted-foreground flex items-center gap-2 text-sm"><BotIcon className="size-4 animate-pulse" /> Looking at your numbers…</div>
          )}
          <div ref={end} />
        </CardContent>
        <form
          className="flex items-end gap-2 border-t p-3"
          onSubmit={(e) => { e.preventDefault(); send(text); }}
        >
          <Textarea
            aria-label="Your question"
            rows={1}
            maxLength={2000}
            className="max-h-40 min-h-10 resize-none"
            placeholder="Ask about your spending, budgets, goals…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
          />
          <Button type="submit" size="icon" aria-label="Send" disabled={busy || !text.trim()}><SendIcon /></Button>
        </form>
      </Card>
      {error && <div className="mt-3"><Alert kind="error">{error}</Alert></div>}
    </>
  );
}

function Bubble({ m }: { m: CoachMsg }) {
  const mine = m.role === "user";
  return (
    <div className={cn("flex gap-2", mine && "flex-row-reverse")}>
      <div className={cn("flex size-7 shrink-0 items-center justify-center rounded-full", mine ? "bg-primary text-primary-foreground" : "bg-muted")}>
        {mine ? <UserRoundIcon className="size-4" /> : <BotIcon className="size-4" />}
      </div>
      <div className={cn("max-w-[85%] space-y-1", mine && "text-right")}>
        <div className={cn("rounded-2xl px-3 py-2 text-left text-sm whitespace-pre-line", mine ? "bg-primary text-primary-foreground" : "bg-muted")}>{m.content}</div>
        {!mine && (m.meta.tools?.length || m.meta.source === "guardrail") ? (
          <p className="text-muted-foreground text-xs">
            {m.meta.source === "guardrail" ? "Safety rule applied" : `Checked your ${m.meta.tools!.map((t) => TOOL_LABEL[t] ?? t).join(", ")}`}
            {m.meta.source === "helper" && " · built-in helper"}
            {m.meta.source === "ai" && " · AI"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
