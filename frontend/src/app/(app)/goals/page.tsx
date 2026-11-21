import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Goals · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Goals"
      description="Save for the things that matter to you."
      phase="Phase 4"
      bullets={[
        "Create a goal like an emergency fund, a laptop or a holiday",
        "Set a target amount and date and record what you put aside",
        "See your progress and whether you're on track",
      ]}
    />
  );
}
