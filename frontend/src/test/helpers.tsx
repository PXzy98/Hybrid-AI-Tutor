import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { resetCsrf } from "../api/client";
import type { Course, Me } from "../api/endpoints";
import App from "../App";
import { I18nProvider, type Lang } from "../i18n";

export type Call = { method: string; path: string; query: URLSearchParams; headers: Record<string, string>; body: unknown; form?: FormData };
type Handler = (call: Call) => unknown;

export const reply = (body: unknown, status = 200) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** Stubs fetch with `"METHOD /path"` routes (path without /api/v2). A route is a body or a function. */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    const path = url.pathname.replace("/api/v2", "");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const raw = init?.body;
    const call: Call = {
      method, path, query: url.searchParams, headers,
      body: typeof raw === "string" ? JSON.parse(raw) : undefined,
      form: raw instanceof FormData ? raw : undefined,
    };
    if (method === "GET" && path === "/auth/csrf") return reply({ csrf_token: "test-token" });
    calls.push(call);
    const route = routes[`${method} ${path}`];
    if (route === undefined) return reply({ detail: `no route ${method} ${path}`, code: "not_found" }, 404);
    const out = typeof route === "function" ? (route as Handler)(call) : route;
    return out instanceof Response ? out : reply(out);
  }));
  return calls;
}

export const ME_STUDENT: Me = { account_id: 1, username: "sam", email: null, display_name: "Sam Student", system_role: "student",
  must_change_password: false, memberships: [] };
export const ME_INSTRUCTOR: Me = { ...ME_STUDENT, account_id: 2, username: "ida", display_name: "Ida Instructor", system_role: "instructor" };
export const COURSE: Course = { id: 1, code: "ECE 1000", title: "Fictional Circuits", term_label: "Fall", course_type: "ece",
  visibility_mode: "B", status: "active", my_role: "student" };
export const MODULES = [{ id: 10, code: "M1", title: "Ohm's law", position: 1, guideline: null }];

export function renderApp(path: string, lang: Lang = "en") {
  resetCsrf();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><I18nProvider lang={lang}><App /></I18nProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

export const studentRoutes = (extra: Record<string, Handler | unknown> = {}) => ({
  "GET /auth/me": ME_STUDENT,
  "GET /courses": [COURSE],
  "GET /courses/1/modules": MODULES,
  "GET /courses/1/conversations": [],
  "GET /courses/1/me/profile": { personalized: false, modules: [], visibility: { mode: "B", acknowledged: true, opted_out: false, visible_to_instructor: true, visible_since: "2026-11-01T00:00:00Z" } },
  ...extra,
});

export const instructorRoutes = (extra: Record<string, Handler | unknown> = {}) => ({
  "GET /auth/me": ME_INSTRUCTOR,
  "GET /courses": [{ ...COURSE, my_role: "instructor" }],
  "GET /courses/1/modules": MODULES,
  ...extra,
});
