import Link from "next/link";
import { Alert } from "@/components/form";
import { ResetForm } from "./reset-form";

export const metadata = { title: "Choose a new password · CASIO" };

export default async function ResetPasswordPage({ searchParams }: PageProps<"/reset-password">) {
  const { token } = await searchParams;
  if (typeof token !== "string" || !token) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Choose a new password</h1>
        <Alert kind="error">This reset link is missing its code. Please use the link from your email.</Alert>
        <Link href="/forgot-password" className="block text-center text-sm font-medium text-primary hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }
  return <ResetForm token={token} />;
}
