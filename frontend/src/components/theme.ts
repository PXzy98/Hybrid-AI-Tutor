import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export type ThemePref = "light" | "dark" | "system";
const THEME_KEY = "tutor.theme";  // interface preference only

export function themePref(): ThemePref {
  try {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // storage blocked: follow the system setting
  }
  return "system";
}

const systemDark = () => !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;

export function applyTheme(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
}

// One choice for the whole page: the desktop sidebar stays mounted (hidden by CSS) next to the mobile sheet, so
// every useTheme() reads the same value and a choice in one menu shows in the other.
let unsaved: ThemePref | null = null;  // the choice when storage is blocked
const listeners = new Set<() => void>();
const read = () => unsaved ?? themePref();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** The theme choice; "system" follows the operating system and stores nothing. */
export function useTheme(): [ThemePref, (next: ThemePref) => void] {
  const pref = useSyncExternalStore(subscribe, read, read);
  useEffect(() => {
    applyTheme(pref);
    if (pref !== "system" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => applyTheme("system");
    query.addEventListener?.("change", follow);
    return () => query.removeEventListener?.("change", follow);
  }, [pref]);
  // a choice made in another tab
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_KEY || e.key === null) listeners.forEach((listener) => listener());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  const setPref = useCallback((next: ThemePref) => {
    try {
      if (next === "system") window.localStorage.removeItem(THEME_KEY);
      else window.localStorage.setItem(THEME_KEY, next);
      unsaved = null;
    } catch {
      unsaved = next;  // not saved; the choice still applies until the page is reloaded
    }
    listeners.forEach((listener) => listener());
  }, []);
  return [pref, setPref];
}

/** Whether the page is dark now (the choice, or the system setting when the choice is "system"). */
export function useIsDark(): boolean {
  const [pref] = useTheme();
  const [systemIsDark, setSystemIsDark] = useState(systemDark);
  useEffect(() => {
    if (!window.matchMedia) return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => setSystemIsDark(!!query.matches);
    query.addEventListener?.("change", follow);
    return () => query.removeEventListener?.("change", follow);
  }, []);
  return pref === "dark" || (pref === "system" && systemIsDark);
}
