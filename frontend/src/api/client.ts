/**
 * Typed fetch wrapper for API v2. Types come from src/api/schema.d.ts (npm run gen:api), generated from the
 * backend's OpenAPI schema, so a backend change shows up here as a type error.
 *
 * Identity lives only in the httpOnly session cookie: every request sends it (credentials: "include"),
 * and nothing about the user is stored in localStorage. Every state-changing request carries the
 * X-CSRF-Token header (api-v2.md section 2).
 */
import type { components } from "./schema";

export type Schemas = components["schemas"];

// Paths below start with /api/v2. VITE_API_URL is only needed when the API is served from another
// origin; in development Vite proxies /api to the backend.
export const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
export const V2 = "/api/v2";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code = "", public retryAfterSeconds?: number) {
    super(message);
  }
}

const CSRF_HEADER = "X-CSRF-Token";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

/** Forgets the token (logout): the next state-changing request fetches an anonymous one. */
export function resetCsrf(token: string | null = null) {
  csrfToken = token;
}

async function csrf(): Promise<string> {
  if (!csrfToken) {
    const res = await fetch(`${BASE}${V2}/auth/csrf`, { credentials: "include" });
    const body = await res.json().catch(() => null);
    csrfToken = body?.csrf_token ?? "";
  }
  return csrfToken as string;
}

function detailOf(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  }
  return "Something went wrong. Please try again.";
}

async function failure(res: Response): Promise<ApiError> {
  const data = await res.json().catch(() => null);
  return new ApiError(res.status, detailOf(data), typeof data?.code === "string" ? data.code : "",
    typeof data?.retry_after_seconds === "number" ? data.retry_after_seconds : undefined);
}

type Body = { json?: unknown; form?: FormData; accept?: string };

/** Sends one request; a stale CSRF token (403 csrf_failed) is replaced once and the request repeated. */
export async function send(method: string, path: string, body: Body = {}, signal?: AbortSignal): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    const headers: Record<string, string> = {};
    if (body.json !== undefined) headers["Content-Type"] = "application/json";
    if (body.accept) headers.Accept = body.accept;
    if (UNSAFE.has(method)) headers[CSRF_HEADER] = await csrf();
    const res = await fetch(BASE + path, {
      method, credentials: "include", headers, signal,
      body: body.form ?? (body.json === undefined ? undefined : JSON.stringify(body.json)),
    });
    const fresh = res.headers.get(CSRF_HEADER);
    if (fresh) csrfToken = fresh; // login and join answer with the new session's token
    if (res.status === 403 && attempt === 0 && UNSAFE.has(method)) {
      const data = await res.clone().json().catch(() => null);
      if (data?.code === "csrf_failed") {
        csrfToken = null;
        continue;
      }
    }
    return res;
  }
}

export async function request<T>(method: string, path: string, json?: unknown): Promise<T> {
  const res = await send(method, V2 + path, { json });
  if (res.status === 204) return undefined as T;
  if (!res.ok) throw await failure(res);
  return (await res.json().catch(() => null)) as T;
}

/** multipart/form-data upload (the browser sets the boundary header). */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await send("POST", V2 + path, { form });
  if (!res.ok) throw await failure(res);
  return (await res.json()) as T;
}

/** A file download: returns the bytes and the file name the server suggested. */
export async function download(path: string): Promise<{ blob: Blob; filename: string }> {
  const res = await send("GET", V2 + path);
  if (!res.ok) throw await failure(res);
  const match = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") ?? "");
  return { blob: await res.blob(), filename: match?.[1] ?? "download" };
}

export { failure };
