import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Money Model · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Money Model"
      description="One clear picture of your whole financial life, kept up to date automatically."
      phase="Phase 4"
      bullets={[
        "Combine your income, spending, savings, debts and goals in one place",
        "Clearly separate real balances, your estimates, plans and forecasts",
        "Look back at monthly snapshots to see how things changed",
      ]}
      meanwhile={{ href: "/profile", label: "fill in your financial profile" }}
    />
  );
}
