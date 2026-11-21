import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Budgets · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Budgets"
      description="Decide how much to spend in each category every month."
      phase="Phase 4"
      bullets={[
        "Set a monthly limit for categories like Food or Shopping",
        "See how much you've spent and how much is left",
        "Get a gentle warning before you go over",
      ]}
    />
  );
}
