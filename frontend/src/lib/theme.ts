// Light / dark theme, remembered in this browser. The root layout applies it
// before first paint; these helpers change it afterwards.
export type ThemeChoice = "light" | "dark" | "system";
const KEY = "casio-theme";

export function readTheme(): ThemeChoice {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function isDark(choice: ThemeChoice): boolean {
  return choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
}

export function applyTheme(choice: ThemeChoice) {
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* private mode: still switch for this visit */
  }
  const root = document.documentElement;
  const dark = isDark(choice);
  // A short class lets colours fade instead of snapping.
  root.classList.add("theme-switching");
  root.classList.toggle("dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
  window.setTimeout(() => root.classList.remove("theme-switching"), 450);
  window.dispatchEvent(new CustomEvent("casio-theme", { detail: choice }));
}
