"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogOutIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      className="w-full"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await api("/auth/logout", {});
        router.replace("/login");
        router.refresh();
      }}
    >
      <LogOutIcon />
      {busy ? "Logging out…" : "Log out"}
    </Button>
  );
}
