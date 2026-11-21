"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, PasswordField, SubmitButton, TextField } from "@/components/form";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { api, safeNext, type User } from "@/lib/api";

export function LoginForm({ next, justReset }: { next?: string; justReset: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setFields({});
    const res = await api<User>("/auth/login", {
      email: form.get("email"),
      password: form.get("password"),
      remember_me: form.get("remember_me") === "on",
    });
    if (res.ok) {
      router.replace(safeNext(next));
      router.refresh();
      return;
    }
    setBusy(false);
    setError(res.message);
    setFields(res.fields);
  }

  return (
    <>
      <h1 className="text-xl font-semibold">Log in</h1>
      <p className="mt-1 text-sm text-muted-foreground">Welcome back. Enter your details to continue.</p>
      <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
        {justReset && <Alert kind="success">Your password has been changed. Log in with your new password.</Alert>}
        {error && <Alert kind="error">{error}</Alert>}
        <TextField label="Email" name="email" type="email" autoComplete="email" required error={fields.email} />
        <PasswordField label="Password" name="password" autoComplete="current-password" required error={fields.password} />
        <div className="flex items-center justify-between gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Checkbox id="remember_me" name="remember_me" />
            <Label htmlFor="remember_me" className="font-normal">
              Remember me for 30 days
            </Label>
          </div>
          <Link href="/forgot-password" className="font-medium text-primary hover:underline">
            Forgot password?
          </Link>
        </div>
        <SubmitButton busy={busy} busyText="Logging in…">
          Log in
        </SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        New to CASIO?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create an account
        </Link>
      </p>
    </>
  );
}
