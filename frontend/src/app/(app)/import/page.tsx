import { ImportView } from "./import-view";
import { ReviewView } from "./review-view";

export const metadata = { title: "Import Statements · CASIO" };

export default async function Page({ searchParams }: { searchParams: Promise<{ batch?: string }> }) {
  const { batch } = await searchParams;
  return batch ? <ReviewView batchId={batch} /> : <ImportView />;
}
