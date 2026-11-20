import { PanelLeft } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useMatch } from "react-router-dom";

import type { Me } from "@/api/endpoints";
import { roleIn, useCourses } from "@/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/i18n";
import ErrorBoundary from "./ErrorBoundary";
import Sidebar from "./shell/Sidebar";
import UserMenu from "./shell/UserMenu";

const SIDEBAR_KEY = "tutor.sidebar";  // interface preference only
const DESKTOP_QUERY = "(min-width: 48rem)";  // Tailwind md: the sidebar instead of the sheet

function storedCollapsed() {
  try {
    return window.localStorage.getItem(SIDEBAR_KEY) === "collapsed";
  } catch {
    return false;
  }
}

/** Full-height shell: sidebar (a sheet on small screens), a quiet top bar with the page h1, the scrolling content
 *  and the disclaimer. Only the content scrolls. */
export default function AppShell({ me }: { me: Me }) {
  const { t } = useI18n();
  const courses = useCourses();
  const location = useLocation();
  const match = useMatch("/courses/:courseId/*");
  const courseId = match ? Number(match.params.courseId) : null;
  const tab = match?.params["*"]?.split("/")[0] || undefined;
  const current = courses.data?.find((c) => c.id === courseId);
  const student = !!current && roleIn(current, me) === "student";
  const showSidebar = !me.must_change_password;
  const [collapsed, setCollapsedState] = useState(storedCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next);
    try {
      if (next) window.localStorage.setItem(SIDEBAR_KEY, "collapsed");
      else window.localStorage.removeItem(SIDEBAR_KEY);
    } catch {
      // not saved; the choice still applies until the page is reloaded
    }
  }, []);

  // the mobile sheet closes on navigation
  useEffect(() => setMobileOpen(false), [location.pathname, location.search, location.key]);

  // and when the window grows to the desktop layout: md:hidden hides only its content, not its overlay
  useEffect(() => {
    const desktop = window.matchMedia?.(DESKTOP_QUERY);
    if (!desktop) return;
    const close = () => {
      if (desktop.matches) setMobileOpen(false);
    };
    desktop.addEventListener?.("change", close);
    return () => desktop.removeEventListener?.("change", close);
  }, []);

  const sidebarProps = { me, current, student, tab };

  return (
    <div className="flex h-dvh overflow-hidden">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground">{t("nav.skip")}</a>
      {showSidebar && !collapsed && (
        <aside aria-label={t("nav.sidebar")} className="hidden w-66 shrink-0 border-r bg-sidebar md:block">
          <Sidebar {...sidebarProps} onCollapse={() => setCollapsed(true)} />
        </aside>
      )}
      {showSidebar && (
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" aria-describedby={undefined} className="bg-sidebar p-0 md:hidden">
            <SheetTitle className="sr-only">{t("nav.sidebar")}</SheetTitle>
            <Sidebar {...sidebarProps} />
          </SheetContent>
        </Sheet>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={`flex h-12 shrink-0 items-center gap-2 border-b bg-background px-3 sm:px-4 ${showSidebar && !current && !collapsed ? "md:hidden" : ""}`}>
          {showSidebar && (
            <Tooltip content={t("nav.expand")}>
              <Button type="button" variant="ghost" size="icon-sm" className={collapsed ? "text-muted-foreground" : "text-muted-foreground md:hidden"}
                      aria-label={t("nav.expand")} aria-expanded={false}
                      onClick={() => (window.matchMedia?.(DESKTOP_QUERY).matches ? setCollapsed(false) : setMobileOpen(true))}>
                <PanelLeft aria-hidden />
              </Button>
            </Tooltip>
          )}
          {current && (
            <>
              <h1 className="min-w-0 truncate text-base">
                <span className="font-semibold">{current.code}</span>{" "}
                <span className="text-muted-foreground">{current.title}</span>
              </h1>
              <Badge variant="secondary" className="shrink-0">{t(student ? "role.student" : "role.instructor")}</Badge>
              {current.status === "archived" && <Badge variant="warning" className="shrink-0">{t("course.archived")}</Badge>}
            </>
          )}
          {!showSidebar && <div className="ml-auto"><UserMenu me={me} compact /></div>}
        </header>
        <main id="main" tabIndex={-1} className="min-h-0 flex-1 overflow-y-auto outline-hidden">
          <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-6 [overflow-wrap:anywhere] sm:px-6">
            <ErrorBoundary><Outlet /></ErrorBoundary>
          </div>
        </main>
        <div role="note" className="shrink-0 px-4 py-1.5 text-center text-xs text-muted-foreground">
          {t("app.disclaimer")}
        </div>
      </div>
    </div>
  );
}
