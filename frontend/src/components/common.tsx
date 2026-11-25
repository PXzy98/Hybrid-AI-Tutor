import { Check, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

/** The fixed sentences of the announcement and quiz endpoints in the UI's language (the server sentence is English). The
 *  privacy refusal names the entity types only, never the text. */
function serverSentence(message: string, t: ReturnType<typeof useI18n>["t"]): string | null {
  const found = /^the privacy scan found student data: (.+)$/i.exec(message);
  if (found) return t("error.privacyFound", { types: found[1] });
  const fixed: Record<string, MessageKey> = {
    "the title cannot be empty": "error.titleEmpty",
    "the course is archived": "error.courseArchived",
    "announcement not found": "error.announcementGone",
    "options must differ": "error.optionsDiffer",
  };
  const key = fixed[message.toLowerCase()] as MessageKey | undefined;
  return key ? t(key) : null;
}

/** A failed request, shown with the server's English sentence (the codes below get a translated one). */
export function ErrorNote({ error, id }: { error: unknown; id?: string }) {
  const { t } = useI18n();
  if (!error) return null;
  let text = error instanceof Error ? error.message : t("app.serverUnreachable");
  if (error instanceof ApiError) {
    if (error.code === "model_failed") text = t("error.modelFailed");
    if (error.code === "model_busy") text = t("error.modelBusy");
    if (error.code === "usage_limit") text = t("error.usageLimit", { s: error.retryAfterSeconds ?? 0 });
    if (error.code === "settings_applying") text = t("error.settingsApplying");
    text = serverSentence(error.message, t) ?? text;
  }
  // a server sentence may start in lower case ("an account with this e-mail exists"); a 409 is not always a
  // change by someone else (duplicates, a quiz already answered), so its own sentence is shown as it is
  text = text.charAt(0).toUpperCase() + text.slice(1);
  return <Alert variant="destructive" role="alert" id={id} icon>{text}</Alert>;
}

/** The head of a page or section: title, one line of description, actions on the right. The course sections are
 *  level 2 (the h1 is in the top bar); a page outside a course passes level 1. */
export function PageHeader({ title, description, actions, level = 2 }:
  { title: ReactNode; description?: ReactNode; actions?: ReactNode; level?: 1 | 2 }) {
  const Heading = level === 1 ? "h1" : "h2";
  // a course section sets its own title, with the course code, in the course page
  useDocumentTitle(level === 1 && typeof title === "string" ? title : undefined);
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 space-y-1">
        <Heading className={level === 1 ? "text-xl font-semibold tracking-tight" : "text-base font-semibold"}>{title}</Heading>
        {description && <p className="max-w-prose text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-end gap-2">{actions}</div>}
    </div>
  );
}

const SKELETONS = {
  list: () => (
    <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}</div>
  ),
  table: () => (
    <div className="space-y-px overflow-hidden rounded-lg border">
      <Skeleton className="h-9 w-full rounded-none" />
      {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full rounded-none opacity-60" />)}
    </div>
  ),
  cards: () => (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div>
  ),
  form: () => (
    <div className="max-w-2xl space-y-4">
      {[0, 1, 2].map((i) => <div key={i} className="space-y-2"><Skeleton className="h-4 w-32" /><Skeleton className="h-9 w-full" /></div>)}
    </div>
  ),
  chat: () => (
    <div className="space-y-6">
      <Skeleton className="ml-auto h-10 w-2/5 rounded-2xl" />
      <div className="space-y-2"><Skeleton className="h-4 w-1/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /></div>
    </div>
  ),
};

/** Loading state: skeletons shaped like the content, and the loading text for assistive technology. */
export function Loading({ variant = "list" }: { variant?: keyof typeof SKELETONS }) {
  const { t } = useI18n();
  const Shape = SKELETONS[variant];
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">{t("app.loading")}</span>
      <Shape />
    </div>
  );
}

/** Nothing to show yet: an icon, a short title, the explaining sentence and, where there is one, the next step. */
export function EmptyState({ icon: Icon, title, children, action }:
  { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-xl border border-dashed px-6 py-10 text-center">
      <span aria-hidden className="mb-2 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </span>
      <p className="text-sm font-semibold">{title}</p>
      {children && <p className="max-w-sm text-sm text-muted-foreground">{children}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/** A single number with its label, for the class overview. */
export function StatCard({ label, value, icon: Icon }: { label: string; value: ReactNode; icon?: LucideIcon }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{label}</p>
        {Icon && <Icon aria-hidden className="size-4 text-muted-foreground" />}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

/** A radio or checkbox option as a full-width selectable row; the native input stays visible. */
export const choiceRow = (selected: boolean) =>
  `flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring ${
    selected ? "border-primary bg-primary-soft" : "bg-card hover:bg-accent"}`;

/** A success line ("Saved", "Plan saved"): an icon and the text, announced politely. */
/** The class of a label whose field is required: a visible marker (CSS, so the label text stays the same). */
export const REQUIRED_LABEL = "after:ml-0.5 after:text-destructive after:content-['*']";

/** A short hint next to a disabled Save that says what is missing ("Fill in the title."). */
export function SaveHint({ children, id }: { children: ReactNode; id?: string }) {
  return <p id={id} className="text-xs text-muted-foreground">{children}</p>;
}

/** The character count of a text field, shown once it is near the limit (80 %). */
export function CharCount({ value, max }: { value: string; max: number }) {
  const { t } = useI18n();
  if (value.length < max * 0.8) return null;
  return <p className={`text-xs ${value.length >= max ? "text-destructive" : "text-muted-foreground"}`} aria-live="polite">
    {t("form.charCount", { n: value.length, max })}</p>;
}

export function StatusText({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="flex items-center gap-1.5 text-sm text-success">
      <Check aria-hidden className="size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
