"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, PasswordField, SubmitButton } from "@/components/form";
import { api } from "@/lib/api";

export function ResetForm({ token }: { token: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password"));
    const confirm = String(form.get("confirm_password"));
    setError("");
    if (password !== confirm) {
      setFields({ confirm_password: "The two passwords don't match." });
      return;
    }
    setBusy(true);
    setFields({});
    const res = await api("/auth/reset-password", { token, password, confirm_password: confirm });
    if (res.ok) {
      router.replace("/login?reset=1");
      return;
    }
    setBusy(false);
    setError(res.message);
    setFields(res.fields);
  }

  return (
    <>
      <h1 className="text-xl font-semibold">Choose a new password</h1>
      <p className="mt-1 text-sm text-muted-foreground">For your safety, you&apos;ll be logged out on all your devices.</p>
      <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
        {error && (
          <Alert kind="error">
            {error}{" "}
            {error.includes("expired") && (
              <Link href="/forgot-password" className="font-medium underline">
                Request a new link
              </Link>
            )}
          </Alert>
        )}
        <PasswordField
          label="New password"
          name="password"
          autoComplete="new-password"
          required
          error={fields.password}
          hint="At least 8 characters, with a letter and a number."
        />
        <PasswordField
          label="Confirm new password"
          name="confirm_password"
          autoComplete="new-password"
          required
          error={fields.confirm_password}
        />
        <SubmitButton busy={busy} busyText="Saving…">
          Save new password
        </SubmitButton>
      </form>
    </>
  );
}
