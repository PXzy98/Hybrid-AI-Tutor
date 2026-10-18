/**
 * Typed fetch wrapper. Types come from src/api/schema.d.ts (npm run gen:api), generated from the
 * backend's OpenAPI schema, so a backend change shows up here as a type error.
 *
 * Identity lives only in the httpOnly session cookie: every request sends it (credentials: "include"),
 * and nothing about the user is stored in localStorage.
 */
import type { components } from "./schema";

export type Schemas = components["schemas"];

// Paths in the schema already start with /api/v1. VITE_API_URL is only needed when the API is served
// from another origin; in development Vite proxies /api to the backend.
export const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function detailOf(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  }
  return "Something went wrong. Please try again.";
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailOf(data));
  return data as T;
}

/** multipart/form-data upload (the browser sets the boundary header). */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(BASE + path, { method: "POST", credentials: "include", body: form });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailOf(data));
  return data as T;
}
