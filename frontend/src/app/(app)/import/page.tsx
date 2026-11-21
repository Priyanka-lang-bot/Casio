import { getCurrentUser } from "@/lib/session";
import { ImportView } from "./import-view";
import { ReviewView } from "./review-view";

export const metadata = { title: "Smart Statement Import · CASIO" };

export default async function Page({ searchParams }: { searchParams: Promise<{ batch?: string }> }) {
  const [{ batch }, user] = await Promise.all([searchParams, getCurrentUser()]);
  return batch ? <ReviewView batchId={batch} /> : <ImportView isDemo={!!user?.is_demo} />;
}
