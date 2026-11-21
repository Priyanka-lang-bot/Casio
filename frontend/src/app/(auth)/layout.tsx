import { Card, CardContent } from "@/components/ui/card";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="wallet-bg flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="inline-flex items-center gap-2 text-2xl font-extrabold tracking-[0.14em]">
            <span className="app-logo-mark" aria-hidden="true">C</span> CASIO
          </p>
          <p className="text-muted-foreground mt-2 text-sm">Your personal financial intelligence, in one wallet.</p>
        </div>
        <Card className="shadow-xl shadow-slate-900/10">
          <CardContent className="sm:px-8">{children}</CardContent>
        </Card>
      </div>
    </main>
  );
}
