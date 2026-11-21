import { ComingSoon } from "@/components/coming-soon";

export const metadata = { title: "Import Statements · CASIO" };

export default function Page() {
  return (
    <ComingSoon
      title="Import Statements"
      description="Bring in transactions from your bank instead of typing them one by one."
      phase="Next up: Phase 2"
      bullets={[
        "Upload a CSV or PDF bank statement, or paste bank SMS messages",
        "See every transaction CASIO found before anything is saved",
        "Fix dates, amounts or categories, and skip duplicates",
        "Know exactly which file each transaction came from",
      ]}
      meanwhile={{ href: "/transactions", label: "add transactions by hand" }}
    />
  );
}
