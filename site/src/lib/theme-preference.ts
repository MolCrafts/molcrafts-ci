import { useEffect, useState } from "react";
import type { ThemeMode } from "@molcrafts/ui";

const STORAGE_KEY = "molci.theme";

function preferred(): ThemeMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private mode, blocked storage — fall through to the OS preference */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Light or dark, remembered under the product's own key.
 *
 * Defaults to the OS preference rather than to light, so the first paint
 * matches the rest of the desktop. The UI package's ThemeToggle only renders the switch.
 */
export function useThemePreference(): [ThemeMode, (theme: ThemeMode) => void] {
  const [theme, setTheme] = useState<ThemeMode>(preferred);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* the class is applied either way; only the memory is lost */
    }
  }, [theme]);

  return [theme, setTheme];
}
