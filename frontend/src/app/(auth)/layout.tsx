import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";
import { Card, CardContent } from "@/components/ui/card";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="paper-bg relative flex flex-1 items-center justify-center px-4 py-10">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <Link href="/" className="app-logo justify-center text-2xl" aria-label="CASIO home">
            <span className="app-logo-mark" aria-hidden="true">C</span> CASIO
          </Link>
          <p className="text-muted-foreground mt-2 text-sm">Your personal financial intelligence, in one wallet.</p>
        </div>
        <Card className="shadow-xl shadow-black/10">
          <CardContent className="sm:px-8">{children}</CardContent>
        </Card>
      </div>
    </main>
  );
}
