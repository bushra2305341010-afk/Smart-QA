import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";
const KEY = "saq-theme";

function stored(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

/** Picks light/dark tokens via html[data-theme]; "system" follows prefers-color-scheme. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(stored);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // Storage can be blocked; the theme still applies for this visit.
    }
  }, [theme]);
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="sr-only">Colour theme</span>
      <select className="field w-28" value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
