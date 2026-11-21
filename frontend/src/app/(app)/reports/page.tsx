import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Monthly Reports · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Monthly Reports"
      description="A short, plain-language review of each month."
      phase="Phase 5"
      bullets={[
        "Income, spending and savings compared with last month",
        "Where your money went and anything unusual",
        "How your budgets and goals did, and ideas to improve",
      ]}
    />
  );
}
