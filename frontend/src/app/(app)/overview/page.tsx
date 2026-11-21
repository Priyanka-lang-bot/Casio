import { getCurrentUser } from "@/lib/session";
import { OverviewView } from "./overview-view";

export const metadata = { title: "Overview · CASIO" };

export default async function OverviewPage() {
  const user = await getCurrentUser();
  return <OverviewView firstName={user?.full_name.split(" ")[0] ?? ""} />;
}
