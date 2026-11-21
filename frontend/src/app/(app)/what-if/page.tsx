import { getCurrentUser } from "@/lib/session";
import { WhatIfView } from "./what-if-view";

export const metadata = { title: "What-If Simulator · CASIO" };

// The demo opens with a ready-made scenario so the result is visible at once.
const DEMO_SCENARIO = "What if I reduce dining expenses by 30%?";

export default async function Page({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const [{ q }, user] = await Promise.all([searchParams, getCurrentUser()]);
  const initial = typeof q === "string" && q.trim() ? q.slice(0, 300) : user?.is_demo ? DEMO_SCENARIO : undefined;
  return <WhatIfView initialQuestion={initial} />;
}
