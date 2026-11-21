import { useI18n } from "@/i18n";

// The interface language picks the locale: Canadian English or Canadian French.
const LOCALES = { en: "en-CA", fr: "fr-CA" } as const;

type Lang = keyof typeof LOCALES;
type Input = string | number | Date;

/** A date in the interface language. */
export function formatDate(value: Input, lang: Lang = "en"): string {
  return new Date(value).toLocaleDateString(LOCALES[lang]);
}

/** A calendar day sent as a date only ("2026-11-16"): shown as that day, without a time-zone shift (parsed as
 *  UTC midnight, it would be the day before west of UTC). */
export function formatDay(value: string, lang: Lang = "en"): string {
  return new Date(value).toLocaleDateString(LOCALES[lang], { timeZone: "UTC" });
}

/** A date and time in the interface language: hours and minutes, no seconds. */
export function formatDateTime(value: Input, lang: Lang = "en"): string {
  return new Date(value).toLocaleString(LOCALES[lang], { dateStyle: "short", timeStyle: "short" });
}

/** The formatters bound to the current interface language. */
export function useFormat() {
  const { lang } = useI18n();
  return {
    date: (value: Input) => formatDate(value, lang),
    day: (value: string) => formatDay(value, lang),
    dateTime: (value: Input) => formatDateTime(value, lang),
  };
}
