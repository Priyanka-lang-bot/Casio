"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { FileTextIcon, MessageSquareTextIcon, ShieldCheckIcon, UploadIcon } from "lucide-react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert } from "@/components/form";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, apiUpload } from "@/lib/api";
import type { ImportBatch, ImportDetail } from "@/lib/types";

const SOURCE_LABEL = { csv: "CSV", pdf: "PDF", sms: "SMS" } as const;
const STATUS: Record<ImportBatch["status"], { text: string; variant: "secondary" | "success" | "outline" | "warning" | "destructive" }> = {
  processing: { text: "Reading…", variant: "secondary" },
  needs_review: { text: "Waiting for your review", variant: "warning" },
  completed: { text: "Saved", variant: "success" },
  failed: { text: "Couldn't read", variant: "destructive" },
  cancelled: { text: "Cancelled / undone", variant: "outline" },
};

export function ImportView() {
  const router = useRouter();
  const [mode, setMode] = useState<"file" | "sms">("file");
  const [smsText, setSmsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failed, setFailed] = useState<ImportDetail | null>(null);
  const [dragging, setDragging] = useState(false);
  const [history, setHistory] = useState<ImportBatch[] | null>(null);
  const [undoing, setUndoing] = useState<ImportBatch | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadHistory = useCallback(async () => {
    const r = await api<ImportBatch[]>("/imports");
    if (r.ok) setHistory(r.data);
  }, []);
  useEffect(() => {
    api<ImportBatch[]>("/imports").then((r) => r.ok && setHistory(r.data));
  }, []);

  async function send(form: FormData) {
    setBusy(true);
    setError("");
    setFailed(null);
    const r = await apiUpload<ImportDetail>("/imports", form);
    setBusy(false);
    if (!r.ok) return setError(r.message);
    if (r.data.status === "failed") {
      setFailed(r.data);
      loadHistory();
      return;
    }
    router.push(`/import?batch=${r.data.id}`);
  }

  function sendFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) return setError("The file is bigger than 10 MB. Try a shorter date range.");
    const form = new FormData();
    form.append("file", file);
    send(form);
  }

  return (
    <>
      <PageHeader
        title="Import Statements"
        description="Bring in transactions from your bank instead of typing them. You'll see everything CASIO found, and can fix it, before anything is saved."
      />

      <div className="mb-4 inline-flex rounded-lg border bg-white p-1" role="tablist" aria-label="How to import">
        {(
          [
            ["file", "Upload a file", UploadIcon],
            ["sms", "Paste bank SMS", MessageSquareTextIcon],
          ] as const
        ).map(([key, label, Icon]) => (
          <button
            key={key}
            role="tab"
            aria-selected={mode === key}
            onClick={() => setMode(key)}
            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium ${mode === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
          >
            <Icon className="size-4" /> {label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4"><Alert kind="error">{error}</Alert></div>}
      {failed && (
        <div className="mb-4 space-y-2">
          {failed.errors.map((e, i) => (
            <Alert key={i} kind="error">{e.message}</Alert>
          ))}
        </div>
      )}

      {mode === "file" ? (
        <Card>
          <CardContent>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                sendFile(e.dataTransfer.files[0]);
              }}
              className={`flex flex-col items-center gap-3 rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors ${dragging ? "border-primary bg-primary/5" : "border-border"}`}
            >
              <FileTextIcon className="text-muted-foreground size-10" />
              <div>
                <p className="font-medium">{busy ? "Reading your statement…" : "Drop your bank statement here"}</p>
                <p className="text-muted-foreground mt-1 text-sm">CSV or PDF statement, or a .txt file of bank SMS. Up to 10 MB.</p>
              </div>
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.pdf,.txt,text/csv,application/pdf,text/plain"
                className="sr-only"
                aria-label="Choose a statement file"
                onChange={(e) => {
                  sendFile(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <Button disabled={busy} onClick={() => fileInput.current?.click()}>
                <UploadIcon /> {busy ? "Reading…" : "Choose a file"}
              </Button>
              <p className="text-muted-foreground max-w-md text-xs">
                PDFs must be the text kind you download from net banking. Scanned or photographed statements can&apos;t be read
                yet. Files are read and then thrown away; only the transactions you save are kept.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Paste your bank SMS messages</CardTitle>
            <CardDescription className="flex items-start gap-2">
              <ShieldCheckIcon className="text-success mt-0.5 size-4 shrink-0" />
              CASIO never reads your SMS inbox. Only what you paste here is used. Put each message on its own line, or leave a
              blank line between them. OTPs and offers are skipped automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Label htmlFor="sms" className="sr-only">SMS messages</Label>
            <Textarea
              id="sms"
              rows={8}
              className="min-h-40"
              placeholder={"Rs.450.00 debited from A/c XX1234 on 02-11-26 to VPA swiggy@icici (Swiggy). Avl Bal Rs.12,070.95\n\nINR 52,000.00 credited to your A/c XX1234 on 01/11/2026 by NEFT from ACME LTD."}
              value={smsText}
              onChange={(e) => setSmsText(e.target.value)}
            />
            <Button
              disabled={busy || !smsText.trim()}
              onClick={() => {
                const form = new FormData();
                form.append("sms_text", smsText);
                send(form);
              }}
            >
              {busy ? "Reading…" : "Read these messages"}
            </Button>
          </CardContent>
        </Card>
      )}

      <p className="text-muted-foreground mt-3 text-sm">
        No statement handy? Try a sample:{" "}
        <a className="text-primary hover:underline" href="/samples/sample-statement.csv" download>CSV</a>{" · "}
        <a className="text-primary hover:underline" href="/samples/sample-6-months.csv" download>6-month CSV (finds subscriptions)</a>{" · "}
        <a className="text-primary hover:underline" href="/samples/sample-statement.pdf" download>PDF</a>{" · "}
        <a className="text-primary hover:underline" href="/samples/sample-sms.txt" download>SMS</a>{" · "}
        <a className="text-primary hover:underline" href="/samples/sample-scanned.pdf" download>scanned PDF</a>
      </p>

      <h2 className="mt-8 mb-3 text-lg font-semibold">Past imports</h2>
      {history === null ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : history.length === 0 ? (
        <p className="text-muted-foreground text-sm">Nothing imported yet.</p>
      ) : (
        <Card className="py-0">
          <ul className="divide-y">
            {history.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{b.original_filename ?? "Pasted SMS messages"}</p>
                  <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-2 text-xs">
                    <Badge variant="secondary">{SOURCE_LABEL[b.source_type]}</Badge>
                    <span>{new Date(b.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
                    <span aria-hidden>·</span>
                    <span>
                      {b.status === "completed" ? `${b.rows_imported} saved` : `${b.rows_found} found`}
                      {b.rows_duplicate > 0 && `, ${b.rows_duplicate} already saved before`}
                    </span>
                  </div>
                </div>
                <Badge variant={STATUS[b.status].variant}>{STATUS[b.status].text}</Badge>
                {b.status === "needs_review" && (
                  <Button size="sm" asChild>
                    <Link href={`/import?batch=${b.id}`}>Continue review</Link>
                  </Button>
                )}
                {b.status === "completed" && (
                  <Button size="sm" variant="outline" onClick={() => setUndoing(b)}>
                    Undo import
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ConfirmDialog
        open={undoing !== null}
        onOpenChange={(o) => !o && setUndoing(null)}
        title="Undo this import?"
        description={undoing ? `The ${undoing.rows_imported} transactions saved from “${undoing.original_filename ?? "pasted SMS"}” will be deleted, including any changes you made to them since. Your totals will update.` : ""}
        confirmLabel="Undo import"
        onConfirm={async () => {
          if (undoing) await api(`/imports/${undoing.id}`, undefined, "DELETE");
          setUndoing(null);
          loadHistory();
        }}
      />
    </>
  );
}
