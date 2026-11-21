import {
  Bot,
  CalendarClock,
  FileText,
  FlaskConical,
  Lightbulb,
  LayoutDashboard,
  Network,
  PiggyBank,
  Receipt,
  Settings,
  Target,
  Upload,
  WandSparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";

// Each card's look: two gradient colours, an accent for the artwork, the
// text colour, and which abstract pattern is printed on it.
export type CardTheme = {
  from: string;
  to: string;
  accent: string;
  ink: "light" | "dark";
  motif: "waves" | "rings" | "orbs" | "stripes" | "grid" | "petals";
};

export type NavItem = {
  href: string;
  label: string;
  short: string; // label printed on the card's top edge
  description: string;
  icon: LucideIcon;
  group: "everyday" | "plan";
  theme: CardTheme;
};

// Every CASIO feature is a card in the wallet. Order = top-to-bottom inside
// each pocket of the wallet, and the order of the "All cards" switcher.
export const NAV: NavItem[] = [
  {
    href: "/overview", label: "Money Overview", short: "Overview", group: "everyday", icon: LayoutDashboard,
    description: "This month's money in, money out and what's left, with charts and recent activity.",
    theme: { from: "#1d2b64", to: "#3b6cf6", accent: "#9ad0ff", ink: "light", motif: "rings" },
  },
  {
    href: "/transactions", label: "Transactions", short: "Transactions", group: "everyday", icon: Receipt,
    description: "Every payment in one list. Search, add, edit and fix categories.",
    theme: { from: "#ff7a6b", to: "#ffb199", accent: "#fff1e6", ink: "dark", motif: "waves" },
  },
  {
    href: "/import", label: "Smart Statement Import", short: "Smart Import", group: "everyday", icon: Upload,
    description: "Upload a CSV or PDF statement or paste bank SMS. CASIO reads, sorts and checks for duplicates.",
    theme: { from: "#0f9b8e", to: "#7ee8c7", accent: "#e6fff7", ink: "dark", motif: "grid" },
  },
  {
    href: "/insights", label: "Spending Insights", short: "Insights", group: "everyday", icon: Lightbulb,
    description: "What changed this month compared with your usual month, and what CASIO noticed.",
    theme: { from: "#f7b733", to: "#ffe08a", accent: "#fff8dc", ink: "dark", motif: "orbs" },
  },
  {
    href: "/budgets", label: "Budgets", short: "Budgets", group: "everyday", icon: PiggyBank,
    description: "Monthly limits per category, how much is left and where the month is heading.",
    theme: { from: "#11734b", to: "#4cc38a", accent: "#d9ffe9", ink: "light", motif: "stripes" },
  },
  {
    href: "/subscriptions", label: "Subscriptions", short: "Subscriptions", group: "everyday", icon: CalendarClock,
    description: "Regular payments found in your statements, with price rises and missed payments.",
    theme: { from: "#b0186b", to: "#ff6fb5", accent: "#ffd6ea", ink: "light", motif: "petals" },
  },
  {
    href: "/rules", label: "Learned Rules", short: "Learned Rules", group: "everyday", icon: WandSparkles,
    description: "Category corrections you chose to keep. You approve every rule, and can pause or delete it.",
    theme: { from: "#7a8b1f", to: "#c8e05a", accent: "#f6ffd0", ink: "dark", motif: "grid" },
  },
  {
    href: "/profile", label: "Financial Profile", short: "Profile", group: "plan", icon: UserRound,
    description: "Your income, regular costs, savings and debts, as you describe them (estimates).",
    theme: { from: "#6c5ce7", to: "#b8a9ff", accent: "#efeaff", ink: "light", motif: "orbs" },
  },
  {
    href: "/money-model", label: "Money Model", short: "Money Model", group: "plan", icon: Network,
    description: "Actuals, estimates and forecasts side by side, so you can see how each number is made.",
    theme: { from: "#0077b6", to: "#56ccf2", accent: "#dff6ff", ink: "light", motif: "rings" },
  },
  {
    href: "/goals", label: "Financial Goals", short: "Goals", group: "plan", icon: Target,
    description: "Savings goals with progress, monthly contributions and a forecast finish date.",
    theme: { from: "#f2711c", to: "#ffb347", accent: "#fff0dc", ink: "dark", motif: "petals" },
  },
  {
    href: "/what-if", label: "What-If Simulator", short: "What-If", group: "plan", icon: FlaskConical,
    description: "Try a change, like spending 30% less on dining, and see its effect on your savings.",
    theme: { from: "#3a1c71", to: "#8e54e9", accent: "#e9dcff", ink: "light", motif: "waves" },
  },
  {
    href: "/coach", label: "AI Finance Coach", short: "Coach", group: "plan", icon: Bot,
    description: "Ask questions in plain words. Answers are worked out from your own data.",
    theme: { from: "#15171c", to: "#3a3f4b", accent: "#7fffd4", ink: "light", motif: "orbs" },
  },
  {
    href: "/reports", label: "Monthly Reports", short: "Reports", group: "plan", icon: FileText,
    description: "A summary of each month: totals, top categories and changes from the month before.",
    theme: { from: "#c0603a", to: "#efc39b", accent: "#fff4ea", ink: "dark", motif: "stripes" },
  },
  {
    href: "/settings", label: "Settings & Privacy", short: "Settings", group: "plan", icon: Settings,
    description: "Account, currency, download all your data or delete it.",
    theme: { from: "#8e959f", to: "#e3e6ea", accent: "#ffffff", ink: "dark", motif: "grid" },
  },
];

export function findNav(pathname: string): NavItem | undefined {
  return NAV.find((n) => pathname === n.href || pathname.startsWith(`${n.href}/`));
}
