import { Moon, Sun } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";

/** A failed request, shown with the server's English sentence (the codes below get a translated one). */
export function ErrorNote({ error }: { error: unknown }) {
  const { t } = useI18n();
  if (!error) return null;
  let text = error instanceof Error ? error.message : t("app.serverUnreachable");
  if (error instanceof ApiError) {
    if (error.code === "usage_limit") text = t("error.usageLimit", { s: error.retryAfterSeconds ?? 0 });
    if (error.code === "settings_applying") text = t("error.settingsApplying");
    if (error.code === "conflict") text = `${t("error.conflict")} ${error.message}`;
  }
  return <Alert variant="destructive" role="alert">{text}</Alert>;
}

/** Page or section heading with an optional description. */
export function SectionTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="space-y-1">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <p className="text-sm text-muted-foreground">{children}</p>}
    </div>
  );
}

const THEME_KEY = "tutor.theme";

function storedTheme(): "light" | "dark" {
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // storage blocked: follow the system setting
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<"light" | "dark">(storedTheme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // not saved; the choice still applies until the page is reloaded
    }
  }
  return (
    <Button type="button" variant="ghost" size="icon" onClick={toggle} aria-label={t(theme === "dark" ? "theme.light" : "theme.dark")}>
      {theme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
