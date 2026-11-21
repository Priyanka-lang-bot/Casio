import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "What-If Simulator · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="What-If Simulator"
      description="Try out changes before you make them."
      phase="Phase 4"
      bullets={[
        "Ask things like “What if my rent goes up by ₹3,000?”",
        "Compare your current path with the new one side by side",
        "See how the change affects your goals (an estimate, not a promise)",
      ]}
    />
  );
}
