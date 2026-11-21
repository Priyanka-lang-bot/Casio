import { getCurrentUser } from "@/lib/session";
import { WalletView } from "./wallet-view";

export const metadata = { title: "Wallet · CASIO" };

export default async function WalletPage() {
  const user = await getCurrentUser();
  return <WalletView firstName={user?.full_name.split(" ")[0] ?? ""} isDemo={!!user?.is_demo} />;
}
