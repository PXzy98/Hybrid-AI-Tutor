import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { askStream, type RoutingEvent } from "../api/askStream";
import { resetCsrf } from "../api/client";
import { COURSE, ME_STUDENT, mockApi, reply, renderApp, studentRoutes } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const answer = {
  session_id: "c-1", conversation_id: "c-1", answer: "Voltage is **current times resistance**.", model_used: "local-model",
  route_target: "local", sources: [{ title: "Lecture 1, slide 4", source: "lecture1.pdf", kc_ids: [] }], checks: [], warnings: [],
  timings_ms: {}, routing_progress: [{ stage: "embedding", status: "completed", elapsed_ms: 4 }], routing_details: null,
};
const sse = (...frames: [string, unknown][]) =>
  new Response(frames.map(([k, d]) => `event: ${k}\ndata: ${JSON.stringify(d)}\n\n`).join(""), { headers: { "Content-Type": "text/event-stream" } });

describe("join a course", () => {
  it("creates the account with the invitation code and sends the CSRF token", async () => {
    let loggedIn = false;
    const calls = mockApi(studentRoutes({
      "GET /auth/me": () => (loggedIn ? ME_STUDENT : reply({ detail: "Not logged in", code: "forbidden" }, 401)),
      "POST /auth/join": () => { loggedIn = true; return reply({ course_id: 1, me: ME_STUDENT }); },
    }));
    renderApp("/join");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Invitation code"), "ABCD-1234");
    await user.type(screen.getByLabelText("E-mail address"), "sam@example.test");
    await user.type(screen.getByLabelText("Your name"), "Sam Student");
    await user.type(screen.getByLabelText("Choose a password"), "a-long-fictional-pass");
    await user.click(screen.getByRole("button", { name: "Join" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/auth/join")).toBe(true));
    const join = calls.find((c) => c.path === "/auth/join")!;
    expect(join.headers["X-CSRF-Token"]).toBe("test-token");
    expect(join.body).toEqual({ code: "ABCD-1234", email: "sam@example.test", display_name: "Sam Student", password: "a-long-fictional-pass" });
    expect(await screen.findByRole("heading", { name: /ECE 1000/ })).toBeInTheDocument();
  });

  it("asks a logged-in student for the code only", async () => {
    const calls = mockApi(studentRoutes({ "POST /auth/join": () => reply({ course_id: 1, me: ME_STUDENT }) }));
    renderApp("/join");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Invitation code"), "ABCD-1234");
    expect(screen.queryByLabelText("E-mail address")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Join" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/auth/join")?.body).toEqual({ code: "ABCD-1234" }));
  });
});

describe("chat", () => {
  it("streams the answer, labels it local, renders Markdown and keeps routing steps collapsed", async () => {
    const calls = mockApi(studentRoutes({
      "POST /courses/1/ask/stream": () => sse(
        ["meta", { request_id: "r", conversation_id: "c-1", show_progress: true, method: "lr" }],
        ["progress", { stage: "embedding", status: "running", elapsed_ms: 1 }],
        ["result", answer], ["done", {}]),
    }));
    renderApp("/courses/1/chat?module=10");
    const user = userEvent.setup();
    expect(await screen.findByText(/may be sent to a cloud model/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your question"), "What is Ohm's law?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    const strong = await screen.findByText("current times resistance");
    expect(strong.tagName).toBe("STRONG");
    expect(screen.getByText("Local model")).toBeInTheDocument();
    expect(screen.getByText(/Lecture 1, slide 4/)).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: /Routing steps/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: "Routing progress" })).not.toBeInTheDocument();
    await user.click(toggle);
    expect(await screen.findByRole("region", { name: "Routing progress" })).toBeInTheDocument();

    const ask = calls.find((c) => c.path === "/courses/1/ask/stream")!;
    expect(ask.method).toBe("POST");
    expect(ask.headers["X-CSRF-Token"]).toBe("test-token");
    expect(ask.body).toMatchObject({ question: "What is Ohm's law?", module_id: 10 });
  });

  it("labels a cloud answer", async () => {
    mockApi(studentRoutes({
      "POST /courses/1/ask/stream": () => sse(["result", { ...answer, route_target: "cloud" }], ["done", {}]),
    }));
    renderApp("/courses/1/chat");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Your question"), "Explain resonance");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Cloud model")).toBeInTheDocument();
  });

  it("shows a stream error as an alert", async () => {
    mockApi(studentRoutes({ "POST /courses/1/ask/stream": () => sse(["error", { detail: "The model is busy." }], ["done", {}]) }));
    renderApp("/courses/1/chat");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Your question"), "Explain resonance");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The model is busy.");
  });
});

describe("my progress", () => {
  it("shows bands only and the read-only plan, and records the acknowledgement", async () => {
    const visibility = { mode: "B", acknowledged: false, opted_out: false, visible_to_instructor: false };
    const calls = mockApi(studentRoutes({
      "GET /courses/1/me/profile": () => ({
        personalized: true, preferences: { sequencing: "example_first", detail: "concise" },
        modules: [{ module_id: 10, code: "M1", title: "Ohm's law", kcs: [{ kc_id: "K1", name: "Resistance", band: "intermediate" }], misconceptions: [] }],
        visibility, plan: { focus_kcs: ["K1"], goal: "advanced", notes: "Practise with circuits.", updated_at: "2026-11-02T00:00:00Z" },
      }),
      "POST /courses/1/me/visibility": () => ({ ...visibility, acknowledged: true, visible_to_instructor: true }),
    }));
    renderApp("/courses/1/progress");
    expect(await screen.findByText("Resistance")).toBeInTheDocument();
    expect(screen.getByText("intermediate")).toBeInTheDocument();
    const plan = screen.getByText("Learning plan").closest("div")!.parentElement!;
    expect(within(plan).getByText("Practise with circuits.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save plan/ })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "I understand and agree" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/me/visibility")?.body).toEqual({ action: "acknowledge" }));
  });

  it("offers an opt-in again after an opt-out", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/me/profile": { personalized: false, modules: [], visibility: { mode: "B", acknowledged: true, opted_out: true, visible_to_instructor: false } },
    }));
    renderApp("/courses/1/progress");
    expect(await screen.findByRole("button", { name: "Share again" })).toBeInTheDocument();
    expect(screen.getByText("Your instructor cannot see your progress")).toBeInTheDocument();
  });
});

describe("SSE client", () => {
  it("parses split UTF-8, CRLF frames, progress and a final result", async () => {
    resetCsrf(`t`);
    const text = ': heartbeat\r\n\r\nevent: progress\r\ndata: {"stage":"embedding","status":"running","elapsed_ms":1}\r\n\r\n'
      + `event: result\r\ndata: ${JSON.stringify({ ...answer, answer: "réponse très claire — ünïcode ✓" })}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n`;
    const bytes = new TextEncoder().encode(text);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream({ start(controller) {
      for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
      controller.close();
    } }))));
    const events: RoutingEvent[] = [];
    const result = await askStream(COURSE.id, { question: "q", conversation_id: "", language: "en" }, (e) => events.push(e));
    expect(result.answer).toBe("réponse très claire — ünïcode ✓");
    expect(events.map((e) => e.type)).toEqual(["progress", "result"]);
  });

  it("reports an interrupted stream without inventing an answer", async () => {
    resetCsrf("t");
    vi.stubGlobal("fetch", vi.fn(async () => new Response('event: progress\ndata: {"stage":"embedding","status":"running","elapsed_ms":1}\n\n')));
    await expect(askStream(1, { question: "q", conversation_id: "", language: "en" }, () => undefined)).rejects.toThrow("before an answer");
  });

  it("surfaces a server error event", async () => {
    resetCsrf("t");
    vi.stubGlobal("fetch", vi.fn(async () => new Response('event: error\ndata: {"detail":"Cloud unavailable"}\n\n')));
    await expect(askStream(1, { question: "q", conversation_id: "", language: "en" }, () => undefined)).rejects.toThrow("Cloud unavailable");
  });

  it("fetches a fresh CSRF token once when the server rejects the old one", async () => {
    resetCsrf("stale");
    const seen: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/auth/csrf")) return reply({ csrf_token: "fresh" });
      seen.push((init?.headers as Record<string, string>)["X-CSRF-Token"]);
      return seen.length === 1 ? reply({ detail: "bad token", code: "csrf_failed" }, 403)
        : sse(["result", answer], ["done", {}]);
    }));
    await askStream(1, { question: "q", conversation_id: "", language: "en" }, () => undefined);
    expect(seen).toEqual(["stale", "fresh"]);
  });
});
