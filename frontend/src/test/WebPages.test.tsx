import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const web = { id: 5, module_id: null, filename: "web-example-org-pullups.md", size_bytes: 2048, scan_status: "accepted",
  uploaded_at: "2026-11-19T00:00:00Z", source_url: "https://example.org/pullups" };
const materials = (list: unknown[]) => ({ index_version: 1, rebuild_job_id: null, materials: list });

describe("web pages as material (V7)", () => {
  it("adds a page by its address and fetches it again", async () => {
    let list: unknown[] = [];
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/materials": () => materials(list),
      "POST /courses/1/materials/url": () => { list = [web]; return reply({ material: web, job_id: 9 }, 201); },
      "POST /courses/1/materials/5/refetch": () => ({ material: web, job_id: 10 }),
      "GET /courses/1/jobs/9": { id: 9, status: "done", progress: 100 },
      "GET /courses/1/jobs/10": { id: 10, status: "done", progress: 100 },
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Address (https)"), "https://example.org/pullups");
    await user.click(screen.getByRole("button", { name: "Add the page" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/materials/url")?.body)
      .toEqual({ url: "https://example.org/pullups", module_id: null }));
    expect(await screen.findByRole("link", { name: "https://example.org/pullups" })).toHaveAttribute("rel", "noopener noreferrer nofollow");
    await user.click(screen.getByRole("button", { name: "Fetch web-example-org-pullups.md again" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/courses/1/materials/5/refetch" && c.method === "POST")).toBe(true));
  });

  it("shows why a page was refused", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/materials": materials([]),
      "POST /courses/1/materials/url": () => reply({ detail: "an external connection must be a public address", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Address (https)"), "https://intranet.example/x");
    await user.click(screen.getByRole("button", { name: "Add the page" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("must be a public address");
  });

  it("drafts from a web page", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/ai/drafts": [], "GET /courses/1/materials": materials([]),
      "POST /courses/1/ai/drafts/url": () => reply({ id: 7, kind: "custom", module_id: null, status: "generating", content: {}, cited_sources: [],
        error: null, created_by: 2, created_at: "", updated_at: "", request: "Lab ideas", sources: {} }, 202),
      "GET /courses/1/ai/drafts/7": { id: 7, kind: "custom", module_id: null, status: "generating", content: {}, cited_sources: [],
        error: null, created_by: 2, created_at: "", updated_at: "", request: "Lab ideas", sources: {} },
    }));
    renderApp("/courses/1/ai");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("What should be drafted?"), "Lab ideas");
    await user.click(screen.getByLabelText("A web page"));
    await user.type(screen.getByLabelText("Address of the page"), "https://example.org/pullups");
    await user.click(screen.getByRole("button", { name: "Draft with AI" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/ai/drafts/url")?.body).toEqual({
      url: "https://example.org/pullups", kind: "custom", request: "Lab ideas", focus: "", add_to_course: false, module_id: null }));
  });
});
