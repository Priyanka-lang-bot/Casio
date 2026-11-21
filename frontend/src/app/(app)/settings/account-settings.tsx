"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { DownloadIcon, Trash2Icon } from "lucide-react";
import { Alert, PasswordField, TextField } from "@/components/form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";

export function AccountSettings({ name }: { name: string }) {
  const router = useRouter();
  const [fullName, setFullName] = useState(name);
  const [nameMsg, setNameMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [pwErr, setPwErr] = useState<Record<string, string>>({});
  const [pwMsg, setPwMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [del, setDel] = useState({ password: "", confirm: "" });
  const [delErr, setDelErr] = useState("");

  return (
    <>
      <Card>
        <CardHeader><CardTitle>Your name</CardTitle></CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy("name");
              const r = await api("/account/name", { full_name: fullName }, "PATCH");
              setBusy("");
              setNameMsg(r.ok ? { kind: "success", text: "Name saved." } : { kind: "error", text: r.fields.full_name ?? r.message });
              if (r.ok) router.refresh();
            }}
          >
            <div className="flex-1"><TextField label="Full name" value={fullName} maxLength={100} onChange={(e) => setFullName(e.target.value)} /></div>
            <Button type="submit" disabled={busy === "name"}>{busy === "name" ? "Saving…" : "Save"}</Button>
          </form>
          {nameMsg && <div className="mt-3"><Alert kind={nameMsg.kind}>{nameMsg.text}</Alert></div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>Other devices are signed out when you change it.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy("pw");
              setPwErr({});
              const r = await api<{ message: string }>("/account/password", pw);
              setBusy("");
              if (r.ok) {
                setPw({ current_password: "", new_password: "", confirm_password: "" });
                setPwMsg({ kind: "success", text: r.data.message });
              } else {
                setPwErr(r.fields);
                setPwMsg({ kind: "error", text: r.message });
              }
            }}
          >
            <PasswordField label="Current password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
            <PasswordField label="New password" autoComplete="new-password" hint="At least 8 characters, with a letter and a number." error={pwErr.new_password} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required />
            <PasswordField label="Confirm new password" autoComplete="new-password" error={pwErr.confirm_password ? "Passwords don't match." : undefined} value={pw.confirm_password} onChange={(e) => setPw({ ...pw, confirm_password: e.target.value })} required />
            <Button type="submit" disabled={busy === "pw"}>{busy === "pw" ? "Saving…" : "Change password"}</Button>
          </form>
          {pwMsg && <div className="mt-3"><Alert kind={pwMsg.kind}>{pwMsg.text}</Alert></div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Privacy and your data</CardTitle>
          <CardDescription>
            Your data is only visible to you. CASIO never sells it. If AI is switched on, only what&apos;s needed to answer goes to the AI
            provider: transaction descriptions with numbers, UPI IDs and emails removed for categorising, and summary figures for the coach.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Button asChild variant="outline">
            <a href="/api/account/export" download><DownloadIcon /> Download all my data (JSON)</a>
          </Button>
          <Button variant="destructive" onClick={() => { setDel({ password: "", confirm: "" }); setDelErr(""); setDeleteOpen(true); }}>
            <Trash2Icon /> Delete my account
          </Button>
        </CardContent>
      </Card>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete your account?</DialogTitle>
            <DialogDescription>
              This permanently deletes your account and everything in it: transactions, imports, rules, budgets, goals, reports and coach
              chats. It can&apos;t be undone. Download your data first if you want a copy.
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-3"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy("del");
              const r = await api("/account/delete", del);
              setBusy("");
              if (!r.ok) return setDelErr(r.fields.confirm ?? r.message);
              // Full page load on purpose: clears everything held in memory.
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination
              window.location.href = "/login?deleted=1";
            }}
          >
            {delErr && <Alert kind="error">{delErr}</Alert>}
            <PasswordField label="Your password" autoComplete="current-password" value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value })} required />
            <TextField label='Type DELETE to confirm' value={del.confirm} onChange={(e) => setDel({ ...del, confirm: e.target.value })} required />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button>
              <Button type="submit" variant="destructive" disabled={busy === "del" || del.confirm.trim().toUpperCase() !== "DELETE"}>
                {busy === "del" ? "Deleting…" : "Delete everything"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
