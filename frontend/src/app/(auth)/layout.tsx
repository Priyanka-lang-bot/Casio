import { Card, CardContent } from "@/components/ui/card";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <p className="text-primary mb-6 text-center text-2xl font-bold tracking-wide">CASIO</p>
        <Card>
          <CardContent className="sm:px-8">{children}</CardContent>
        </Card>
      </div>
    </main>
  );
}
