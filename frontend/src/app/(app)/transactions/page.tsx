import { TransactionsView } from "./transactions-view";

export const metadata = { title: "Transactions · CASIO" };

export default async function Page({ searchParams }: PageProps<"/transactions">) {
  const { rule_id } = await searchParams;
  return <TransactionsView ruleId={typeof rule_id === "string" ? rule_id : ""} />;
}
