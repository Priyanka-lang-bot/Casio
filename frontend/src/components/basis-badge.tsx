import { Badge } from "@/components/ui/badge";

// Every number in CASIO says where it came from.
const LABELS = {
  actual: { text: "Actual", title: "Calculated from transactions you recorded", variant: "success" },
  estimate: { text: "Your estimate", title: "Based on what you entered in your Financial Profile", variant: "secondary" },
  forecast: { text: "Forecast", title: "A projection, not a guarantee", variant: "outline" },
} as const;

export function BasisBadge({ basis }: { basis: keyof typeof LABELS }) {
  const l = LABELS[basis];
  return (
    <Badge variant={l.variant} title={l.title}>
      {l.text}
    </Badge>
  );
}
