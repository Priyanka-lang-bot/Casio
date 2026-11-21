import { getCurrentUser } from "@/lib/session";
import { SettingsView } from "./settings-view";

export const metadata = { title: "Settings · CASIO" };

export default async function Page() {
  const user = await getCurrentUser();
  return <SettingsView name={user?.full_name ?? ""} email={user?.email ?? ""} />;
}
