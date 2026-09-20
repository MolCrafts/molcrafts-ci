import { Moon, Sun } from "lucide-react";
import { useEffect, useState, type JSX } from "react";

import { Button } from "@/components/ui/button";

type Theme = "light" | "dark";
const STORAGE_KEY = "molci.theme";

function preferred(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private mode, blocked storage — fall through to the OS preference */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Light or dark, remembered.
 *
 * The dark palette has always been defined in tokens.css; nothing could reach
 * it. Defaults to the OS preference rather than to light, so the first paint
 * matches the rest of the desktop.
 */
export function ThemeToggle(): JSX.Element {
  const [theme, setTheme] = useState<Theme>(preferred);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* the class is applied either way; only the memory is lost */
    }
  }, [theme]);

  const next = theme === "dark" ? "light" : "dark";

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="text-muted-foreground"
      onClick={() => setTheme(next)}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
