import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

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

  it("the instructor sees the topics the class finds hard", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/weak-topics": { min_group: 5, weak_below: 0.6, topics: [
        { kc_code: "K1", name: "Resistance", module_id: 10, students: 7, correct_rate: 0.43 }] },
    }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText("43% correct, 7 students")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Draft extra material on Resistance" })).toHaveAttribute("href", "/courses/1/ai");
  });
});
