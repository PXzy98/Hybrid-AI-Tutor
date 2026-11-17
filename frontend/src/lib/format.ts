import { useI18n } from "@/i18n";

// The interface language picks the locale: Canadian English or Canadian French.
const LOCALES = { en: "en-CA", fr: "fr-CA" } as const;

type Lang = keyof typeof LOCALES;
type Input = string | number | Date;

/** A date in the interface language. */
export function formatDate(value: Input, lang: Lang = "en"): string {
  return new Date(value).toLocaleDateString(LOCALES[lang]);
}

/** A date and time in the interface language. */
export function formatDateTime(value: Input, lang: Lang = "en"): string {
  return new Date(value).toLocaleString(LOCALES[lang]);
}

/** The two formatters bound to the current interface language. */
export function useFormat() {
  const { lang } = useI18n();
  return {
    date: (value: Input) => formatDate(value, lang),
    dateTime: (value: Input) => formatDateTime(value, lang),
  };
}
