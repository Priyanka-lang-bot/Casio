"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/form";
import { LogoutButton } from "@/components/logout-button";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { AccountSettings } from "./account-settings";

const CURRENCIES = { INR: "Indian rupee (₹)", USD: "US dollar ($)", EUR: "Euro (€)", GBP: "British pound (£)", AED: "UAE dirham", SGD: "Singapore dollar" };

export function SettingsView({ name, email }: { name: string; email: string }) {
  const [currency, setCurrency] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ currency: string }>("/profile").then((r) => r.ok && setCurrency(r.data.currency));
  }, []);

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid max-w-2xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Your account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">Name:</span> {name}
            </p>
            <p>
              <span className="text-muted-foreground">Email:</span> {email}
            </p>
            <div className="max-w-40 pt-2">
              <LogoutButton />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Currency</CardTitle>
            <CardDescription>
              All your amounts use one currency. It can only be changed before you add transactions, so old amounts are
              never mislabelled.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!currency ? (
              <p className="text-muted-foreground text-sm">Loading…</p>
            ) : (
            <form
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setSaved(false);
                setError("");
                const r = await api("/profile", { currency }, "PATCH");
                setBusy(false);
                if (r.ok) setSaved(true);
                else setError(r.message);
              }}
            >
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="currency">Currency</Label>
                <NativeSelect id="currency" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  {Object.entries(CURRENCIES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <Button type="submit" disabled={busy || !currency}>
                {busy ? "Saving…" : "Save"}
              </Button>
            </form>
            )}
            <div className="mt-3">
              {saved && <Alert kind="success">Currency saved.</Alert>}
              {error && <Alert kind="error">{error}</Alert>}
            </div>
          </CardContent>
        </Card>

        <AccountSettings name={name} />
      </div>
    </>
  );
}
