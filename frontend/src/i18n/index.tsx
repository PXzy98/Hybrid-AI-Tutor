import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { en, type MessageKey } from "./en";
import { fr } from "./fr";

export type Lang = "en" | "fr";
export const LANGS: { id: Lang; label: string }[] = [{ id: "en", label: "English" }, { id: "fr", label: "Français" }];
const MESSAGES = { en, fr };
const LOCALES: Record<Lang, string> = { en: "en-CA", fr: "fr-CA" };
const STORAGE_KEY = "tutor.lang";  // interface language only; nothing about the user is stored

export type T = (key: MessageKey, vars?: Record<string, string | number>) => string;

function translate(lang: Lang): T {
  return (key, vars) => {
    const text = MESSAGES[lang][key] ?? en[key];
    return vars ? text.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m)) : text;
  };
}

/** For text the app writes for the tutor or the instructor AI (a prepared request): it stays English in every
 *  interface language, because the privacy filter, the course search and the course material are English (V17 W23). */
export const tEnglish: T = translate("en");

type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: T; locale: string };
// without a provider (unit tests of single components) the interface is English
const Context = createContext<I18n>({ lang: "en", setLang: () => undefined, t: translate("en"), locale: LOCALES.en });

function initialLang(): Lang {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "fr") return saved;
  } catch {
    // storage blocked: fall back to the browser language
  }
  return navigator.language?.toLowerCase().startsWith("fr") ? "fr" : "en";
}

export function I18nProvider({ children, lang: fixed }: { children: ReactNode; lang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(() => fixed ?? initialLang());
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // not saved; the choice still applies until the page is reloaded
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const value = useMemo(() => ({ lang, setLang, t: translate(lang), locale: LOCALES[lang] }), [lang, setLang]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export const useI18n = () => useContext(Context);

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <span className="sr-only">{t("lang.label")}</span>
      <select className="select-chevron h-8 appearance-none rounded-md border border-input bg-background py-1 pr-7 pl-2 text-sm text-foreground outline-hidden focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30"
              value={lang} aria-label={t("lang.label")} onChange={(e) => setLang(e.target.value as Lang)}>
        {LANGS.map((l) => <option key={l.id} value={l.id} lang={l.id}>{l.label}</option>)}
      </select>
    </label>
  );
}
