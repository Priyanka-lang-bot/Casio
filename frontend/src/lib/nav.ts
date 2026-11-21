import {
  Bot,
  CalendarClock,
  FileText,
  FlaskConical,
  LayoutDashboard,
  Network,
  PiggyBank,
  Receipt,
  Settings,
  Target,
  Upload,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

// The 12 sections of CASIO, in sidebar order.
export const NAV: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/import", label: "Import Statements", icon: Upload },
  { href: "/budgets", label: "Budgets", icon: PiggyBank },
  { href: "/subscriptions", label: "Subscriptions", icon: CalendarClock },
  { href: "/profile", label: "Financial Profile", icon: UserRound },
  { href: "/money-model", label: "Money Model", icon: Network },
  { href: "/goals", label: "Goals", icon: Target },
  { href: "/what-if", label: "What-If Simulator", icon: FlaskConical },
  { href: "/reports", label: "Monthly Reports", icon: FileText },
  { href: "/coach", label: "AI Finance Coach", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

