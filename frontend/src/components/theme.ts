import { useCallback, useEffect, useState } from "react";

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
  document.documentElement.classList.toggle("dark", pref === "dark" || (pref === "system" && systemDark()));
}

/** The theme choice; "system" follows the operating system and stores nothing. */
export function useTheme(): [ThemePref, (next: ThemePref) => void] {
  const [pref, setPrefState] = useState<ThemePref>(themePref);
  useEffect(() => {
    applyTheme(pref);
    if (pref !== "system" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => applyTheme("system");
    query.addEventListener?.("change", follow);
    return () => query.removeEventListener?.("change", follow);
  }, [pref]);
  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    try {
      if (next === "system") window.localStorage.removeItem(THEME_KEY);
      else window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // not saved; the choice still applies until the page is reloaded
    }
  }, []);
  return [pref, setPref];
}
