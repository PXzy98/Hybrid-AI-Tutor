import { Check, Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import { useTheme } from "./theme";

/** A failed request, shown with the server's English sentence (the codes below get a translated one). */
export function ErrorNote({ error, id }: { error: unknown; id?: string }) {
  const { t } = useI18n();
  if (!error) return null;
  let text = error instanceof Error ? error.message : t("app.serverUnreachable");
  if (error instanceof ApiError) {
    if (error.code === "usage_limit") text = t("error.usageLimit", { s: error.retryAfterSeconds ?? 0 });
    if (error.code === "settings_applying") text = t("error.settingsApplying");
    if (error.code === "conflict") text = `${t("error.conflict")} ${error.message}`;
  }
  return <Alert variant="destructive" role="alert" id={id} icon>{text}</Alert>;
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

/** A success line ("Saved", "Plan saved"): an icon and the text, announced politely. */
export function StatusText({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="flex items-center gap-1.5 text-sm text-success">
      <Check aria-hidden className="size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** Switches between light and dark (the user menu also offers "system"). */
export function ThemeToggle() {
  const { t } = useI18n();
  const [pref, setPref] = useTheme();
  const dark = pref === "dark" || (pref === "system" && document.documentElement.classList.contains("dark"));
  return (
    <Button type="button" variant="ghost" size="icon" onClick={() => setPref(dark ? "light" : "dark")}
            aria-label={t(dark ? "theme.light" : "theme.dark")}>
      {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
