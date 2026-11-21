import Link from "next/link";
import { ConstructionIcon } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

// Honest placeholder for sections that are planned but not built yet.
// It never shows made-up numbers.
export function ComingSoon({
  title,
  description,
  phase,
  bullets,
  meanwhile,
}: {
  title: string;
  description: string;
  phase: string;
  bullets: string[];
  meanwhile?: { href: string; label: string };
}) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <ConstructionIcon className="text-muted-foreground size-5" />
            <span className="font-medium">Not built yet</span>
            <Badge variant="secondary">{phase}</Badge>
          </div>
          <div>
            <p className="text-muted-foreground mb-2 text-sm">When it&apos;s ready, you&apos;ll be able to:</p>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
          {meanwhile && (
            <p className="text-sm">
              In the meantime:{" "}
              <Link href={meanwhile.href} className="text-primary font-medium hover:underline">
                {meanwhile.label}
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </>
  );
}
