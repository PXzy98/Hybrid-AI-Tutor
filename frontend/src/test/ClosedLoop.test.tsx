import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const ANSWER = {
  session_id: "c-1", conversation_id: "c-1", answer: "Another explanation.", model_used: "local-model", route_target: "local",
  sources: [], checks: [], warnings: [], timings_ms: {}, routing_progress: [], routing_details: null,
};
const sse = (...frames: [string, unknown][]) =>
  new Response(frames.map(([k, d]) => `event: ${k}\ndata: ${JSON.stringify(d)}\n\n`).join(""), { headers: { "Content-Type": "text/event-stream" } });

describe("closed loop (V8)", () => {
  it("a weak topic on My progress opens the chat with another explanation ready to send", async () => {
    const calls = mockApi(studentRoutes({
      "GET /courses/1/me/profile": { personalized: true, modules: [{ module_id: 10, code: "M1", title: "Ohm's law", misconceptions: [],
        kcs: [{ kc_id: "K1", name: "Resistance", band: "basic" }, { kc_id: "K2", name: "Current", band: "advanced" }] }],
        visibility: { mode: "A", acknowledged: false, opted_out: false, visible_to_instructor: false, visible_since: null } },
    }));
    renderApp("/courses/1/progress");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "Explain Resistance another way" }));
    expect(screen.queryByRole("link", { name: "Explain Current another way" })).not.toBeInTheDocument();
    const box = await screen.findByLabelText("Your question");
    await waitFor(() => expect(box).toHaveValue(
      "Explain Resistance in another way than before: a different explanation, a new example, and where I can read more about it."));
    expect(calls.some((c) => c.path.includes("/ask"))).toBe(false);  // the student decides to send it
  });

  it("the prepared request is used once: a new chat after sending it starts empty", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/me/profile": { personalized: true, modules: [{ module_id: 10, code: "M1", title: "Ohm's law", misconceptions: [],
        kcs: [{ kc_id: "K1", name: "Resistance", band: "basic" }] }],
        visibility: { mode: "A", acknowledged: false, opted_out: false, visible_to_instructor: false, visible_since: null } },
      "POST /courses/1/ask/stream": () => sse(["result", ANSWER], ["done", {}]),
    }));
    renderApp("/courses/1/progress");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "Explain Resistance another way" }));
    await waitFor(() => expect(screen.getByLabelText("Your question")).not.toHaveValue(""));
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Another explanation.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New chat" }));
    await waitFor(() => expect(screen.queryByText("Another explanation.")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Your question")).toHaveValue("");
  });

  it("the instructor sees the topics the class finds hard", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/weak-topics": { min_group: 5, weak_below: 0.6, topics: [
        { kc_code: "K1", name: "Resistance", module_id: 10, students: 7, correct_rate: 0.43 }] },
    }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText("43% correct, 7 students")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Draft extra material on Resistance" })).toHaveAttribute("href", "/courses/1/ai");
  });

  it("Draft extra material opens the AI assistant prepared for the topic and its module", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/weak-topics": { min_group: 5, weak_below: 0.6, topics: [
        { kc_code: "K1", name: "Resistance", module_id: 10, students: 7, correct_rate: 0.43 }] },
      "GET /courses/1/ai/drafts": [],
    }));
    renderApp("/courses/1/overview");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "Draft extra material on Resistance" }));
    const focus = await screen.findByLabelText("Focus (optional)");
    expect(focus).toHaveValue("Extra material on Resistance for the whole class: another explanation than in the course material, worked examples and a few practice questions with answers.");
    await waitFor(() => expect(screen.getByLabelText("Module")).toHaveValue("10"));
    await user.click(screen.getByRole("button", { name: "Draft with AI" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/ai/drafts"))?.body)
      .toMatchObject({ module_id: 10, focus: expect.stringContaining("Resistance") }));
  });
});
