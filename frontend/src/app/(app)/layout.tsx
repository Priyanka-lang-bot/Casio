import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-nav";
import { getCurrentUser } from "@/lib/session";

// Every page inside (app) is protected: this checks the session with the
// backend on each request and sends signed-out visitors to /login.
export default async function AppLayout({ children }: LayoutProps<"/">) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <AppShell userName={user.full_name} email={user.email} isDemo={!!user.is_demo}>
      {children}
    </AppShell>
  );
}
