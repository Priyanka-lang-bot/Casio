"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { MenuIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LogoutButton } from "@/components/logout-button";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-primary/10 text-primary" : "text-foreground/80 hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppNav({ userName, email }: { userName: string; email: string }) {
  const [open, setOpen] = useState(false);

  const userBlock = (
    <div className="space-y-3 border-t p-4">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{userName}</p>
        <p className="text-muted-foreground truncate text-xs">{email}</p>
      </div>
      <LogoutButton />
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="bg-card sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r lg:flex">
        <Link href="/overview" className="text-primary px-6 py-5 text-xl font-bold tracking-wide">
          CASIO
        </Link>
        <div className="flex-1 overflow-y-auto px-3">
          <NavLinks />
        </div>
        {userBlock}
      </aside>

      {/* Mobile / tablet top bar */}
      <header className="bg-card sticky top-0 z-30 flex items-center justify-between border-b px-4 py-3 lg:hidden">
        <Link href="/overview" className="text-primary text-lg font-bold tracking-wide">
          CASIO
        </Link>
        <Button variant="ghost" size="icon" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}>
          <MenuIcon />
        </Button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="bg-card absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col shadow-xl">
            <div className="flex items-center justify-between px-4 py-3">
              <span className="text-primary text-lg font-bold tracking-wide">CASIO</span>
              <Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setOpen(false)}>
                <XIcon />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-3">
              <NavLinks onNavigate={() => setOpen(false)} />
            </div>
            {userBlock}
          </div>
        </div>
      )}
    </>
  );
}
