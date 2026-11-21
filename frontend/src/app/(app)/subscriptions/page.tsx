import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Subscriptions · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Subscriptions"
      description="Find the payments that repeat every week, month or year."
      phase="Phase 3"
      bullets={[
        "Automatically spot subscriptions and regular bills in your transactions",
        "See the next expected payment and any price increases",
        "Mark whether you still use a service",
      ]}
    />
  );
}
