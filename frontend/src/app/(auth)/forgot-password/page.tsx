"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, SubmitButton, TextField } from "@/components/form";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [sent, setSent] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setFields({});
    const res = await api<{ message: string }>("/auth/forgot-password", {
      email: new FormData(e.currentTarget).get("email"),
    });
    setBusy(false);
    if (res.ok) setSent(res.data.message);
    else {
      setError(res.message);
      setFields(res.fields);
    }
  }

  return (
    <>
      <h1 className="text-xl font-semibold">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">Enter your email and we&apos;ll send you a link to choose a new password.</p>
      {sent ? (
        <div className="mt-6 space-y-4">
          <Alert kind="success">{sent}</Alert>
          <p className="text-sm text-muted-foreground">The link works for 30 minutes.</p>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
          {error && <Alert kind="error">{error}</Alert>}
          <TextField label="Email" name="email" type="email" autoComplete="email" required error={fields.email} />
          <SubmitButton busy={busy} busyText="Sending…">
            Send reset link
          </SubmitButton>
        </form>
      )}
      <p className="mt-6 text-center text-sm">
        <Link href="/login" className="font-medium text-primary hover:underline">
          Back to log in
        </Link>
      </p>
    </>
  );
}
