import type { CSSProperties } from "react";
import type { NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

// The printed face of one CASIO feature card: gradient, abstract artwork,
// chip, label and a one-line description. Purely visual: the caller makes
// it a link.
export function CardFace({ item, index, className }: { item: NavItem; index: number; className?: string }) {
  const { theme, icon: Icon } = item;
  const style = {
    "--c-from": theme.from,
    "--c-to": theme.to,
    "--c-accent": theme.accent,
  } as CSSProperties;
  return (
    <div className={cn("card-face", `motif-${theme.motif}`, theme.ink === "light" ? "ink-light" : "ink-dark", className)} style={style}>
      <div className="card-art" aria-hidden="true" />
      <div className="card-sheen" aria-hidden="true" />
      <div className="card-band">
        <span className="card-icon" aria-hidden="true">
          <Icon />
        </span>
        <span className="card-label">{item.short}</span>
        <span className="card-no" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
      </div>
      <div className="card-body" aria-hidden="true">
        <div className="card-chip" />
        <p className="card-desc">{item.description}</p>
        <div className="card-foot">
          <span className="card-brand">CASIO</span>
          <span className="card-dots">•••• {item.short.slice(0, 4).toUpperCase()}</span>
        </div>
      </div>
    </div>
  );
}
