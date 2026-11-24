import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const RESTORE_WAIT_MS = 2000;  // a page that loads its data after the back step gets this long to grow

/** The shell scrolls its own content element, not the window, so the browser neither resets nor restores the
 *  position on a route change. This does both: a new page starts at the top, a back or forward step returns to
 *  where that page was left. Only the query string changing (a filter, a tab) or a link to an anchor keeps the
 *  position as it is. */
export function useScrollMemory(scroller: RefObject<HTMLElement | null>) {
  const location = useLocation();
  const navigationType = useNavigationType();
  const positions = useRef(new Map<string, number>());
  const current = useRef(location.key);
  const lastPath = useRef(location.pathname);

  // remember the position of the entry on screen while it is scrolled; read after the change it would already
  // be clamped to the height of the next page
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const save = () => positions.current.set(current.current, el.scrollTop);
    el.addEventListener("scroll", save, { passive: true });
    return () => el.removeEventListener("scroll", save);
  }, [scroller]);

  useLayoutEffect(() => {
    const el = scroller.current;
    current.current = location.key;
    const samePath = lastPath.current === location.pathname;
    lastPath.current = location.pathname;
    if (!el) return;

    const saved = positions.current.get(location.key);
    if (navigationType === "POP") {
      if (saved !== undefined) return restore(el, saved);
      // an entry never seen in this tab (after a reload): start at the top, like a new page
    } else if (samePath || location.hash) {
      return;
    }
    el.scrollTop = 0;
  }, [location.key, location.pathname, location.hash, navigationType, scroller]);
}

/** Scroll to `top`; when the page is not tall enough yet (its data still loading), try again as it grows,
 *  until it fits, the reader scrolls on their own, or the wait is over. */
function restore(el: HTMLElement, top: number) {
  el.scrollTop = top;
  if (Math.abs(el.scrollTop - top) < 1 || typeof ResizeObserver === "undefined") return;
  const content = el.firstElementChild ?? el;
  const observer = new ResizeObserver(() => {
    el.scrollTop = top;
    if (Math.abs(el.scrollTop - top) < 1) stop();
  });
  const stop = () => {
    observer.disconnect();
    window.clearTimeout(timer);
    for (const type of ["wheel", "touchstart", "keydown"]) el.removeEventListener(type, stop);
  };
  const timer = window.setTimeout(stop, RESTORE_WAIT_MS);
  for (const type of ["wheel", "touchstart", "keydown"]) el.addEventListener(type, stop, { passive: true });
  observer.observe(content);
  return stop;
}
