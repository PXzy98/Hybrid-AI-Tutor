import { useEffect } from "react";

export const PRODUCT = "ScholarMind AI";

/** The tab title: the page, the course code if any, then the product name. Parts that are empty are left out and
 *  the product name is not repeated (the login page is just "ScholarMind AI"). */
export function documentTitle(page?: string | null, courseCode?: string | null): string {
  return [page, courseCode, PRODUCT].filter((p, i, all): p is string => !!p && all.indexOf(p) === i).join(" · ");
}

/** Sets document.title while the page is shown, so a screen reader announces the new page after navigating.
 *  `undefined` leaves the title alone (a section header mounted later must not overwrite the page's title);
 *  `null` sets just the product name. */
export function useDocumentTitle(page?: string | null, courseCode?: string | null) {
  useEffect(() => {
    if (page === undefined) return;
    document.title = documentTitle(page, courseCode);
  }, [page, courseCode]);
}
