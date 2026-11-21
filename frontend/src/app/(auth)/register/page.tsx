"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, PasswordField, SubmitButton, TextField } from "@/components/form";
import { api, type User } from "@/lib/api";

// Same rules as the backend, checked here first so people get instant feedback.
// The backend always checks again; this is only for convenience.
function validate(v: Record<string, string>) {
  const errors: Record<string, string> = {};
  if (!v.full_name.trim()) errors.full_name = "Please enter your full name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email.trim())) errors.email = "Please enter a valid email address.";
  if (v.password.length < 8) errors.password = "Password must be at least 8 characters long.";
  else if (!/[A-Za-z]/.test(v.password) || !/\d/.test(v.password))
    errors.password = "Password must include at least one letter and one number.";
  if (v.confirm_password !== v.password) errors.confirm_password = "The two passwords don't match.";
  return errors;
}

export default function RegisterPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setError("");
    const local = validate(values);
    setFields(local);
    if (Object.keys(local).length) return;

    setBusy(true);
    const res = await api<User>("/auth/register", values);
    if (res.ok) {
      router.replace("/overview");
      router.refresh();
      return;
    }
    setBusy(false);
    setError(res.message);
    setFields(res.fields);
  }

  return (
    <>
      <h1 className="text-xl font-semibold">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">It takes less than a minute.</p>
      <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
        {error && (
          <Alert kind="error">
            {error}
            {error.includes("already exists") && (
              <>
                {" "}
                <Link href="/login" className="font-medium underline">
                  Log in
                </Link>
              </>
            )}
          </Alert>
        )}
        <TextField label="Full name" name="full_name" autoComplete="name" required error={fields.full_name} />
        <TextField label="Email" name="email" type="email" autoComplete="email" required error={fields.email} />
        <PasswordField
          label="Password"
          name="password"
          autoComplete="new-password"
          required
          error={fields.password}
          hint="At least 8 characters, with a letter and a number."
        />
        <PasswordField
          label="Confirm password"
          name="confirm_password"
          autoComplete="new-password"
          required
          error={fields.confirm_password}
        />
        <SubmitButton busy={busy} busyText="Creating account…">
          Create account
        </SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Log in
        </Link>
      </p>
    </>
  );
}
