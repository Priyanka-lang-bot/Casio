"use client";

import { useId, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { AlertCircleIcon, CheckCircle2Icon, EyeIcon, EyeOffIcon, InfoIcon } from "lucide-react";
import { Alert as UiAlert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
};

export function TextField({ label, error, hint, ...input }: FieldProps) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={!!error} aria-describedby={error || hint ? `${id}-msg` : undefined} {...input} />
      <FieldMessage id={`${id}-msg`} error={error} hint={hint} />
    </div>
  );
}

export function PasswordField({ label, error, hint, ...input }: FieldProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          aria-invalid={!!error}
          aria-describedby={error || hint ? `${id}-msg` : undefined}
          className="pr-20"
          {...input}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="text-primary absolute inset-y-0 right-0 flex items-center gap-1 px-3 text-sm font-medium hover:underline"
        >
          {visible ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      <FieldMessage id={`${id}-msg`} error={error} hint={hint} />
    </div>
  );
}

function FieldMessage({ id, error, hint }: { id: string; error?: string; hint?: string }) {
  if (error)
    return (
      <p id={id} className="text-destructive text-sm">
        {error}
      </p>
    );
  if (hint)
    return (
      <p id={id} className="text-muted-foreground text-sm">
        {hint}
      </p>
    );
  return null;
}

export function SubmitButton({ busy, children, busyText }: { busy: boolean; children: ReactNode; busyText: string }) {
  return (
    <Button type="submit" disabled={busy} size="lg" className="w-full">
      {busy ? busyText : children}
    </Button>
  );
}

export function Alert({ kind, children }: { kind: "error" | "success" | "info"; children: ReactNode }) {
  const variant = { error: "destructive", success: "success", info: "info" } as const;
  const Icon = { error: AlertCircleIcon, success: CheckCircle2Icon, info: InfoIcon }[kind];
  return (
    <UiAlert variant={variant[kind]} role={kind === "error" ? "alert" : "status"}>
      <Icon />
      <AlertDescription className="text-current">{children}</AlertDescription>
    </UiAlert>
  );
}
