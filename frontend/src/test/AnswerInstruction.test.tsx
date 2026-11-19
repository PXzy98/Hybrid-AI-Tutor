import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, reply, renderApp, studentRoutes } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const profile = { personalized: true, modules: [], preferences: { sequencing: "example_first", detail: "concise" },
  visibility: { mode: "A", acknowledged: false, opted_out: false, visible_to_instructor: false, visible_since: null } };

describe("the student's own answer instruction (V15)", () => {
  it("saves it from My progress", async () => {
    const calls = mockApi(studentRoutes({
      "GET /courses/1/me/profile": profile,
      "GET /me/answer-instruction": { text: "" },
      "PUT /me/answer-instruction": (c: { body: { text: string } }) => ({ text: c.body.text }),
    }));
    renderApp("/courses/1/progress");
    const user = userEvent.setup();
    const box = await screen.findByRole("textbox", { name: "How answers should look" });
    await user.type(box, "Always end with a one-line summary.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ text: "Always end with a one-line summary." }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("shows why a text with personal details is refused", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/me/profile": profile,
      "GET /me/answer-instruction": { text: "" },
      "PUT /me/answer-instruction": () => reply({ detail: "remove personal details from the instruction: PERSON" }, 422),
    }));
    renderApp("/courses/1/progress");
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "How answers should look" }), "Call me Ana");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("remove personal details");
  });

  it("is not offered without a profile (no consent)", async () => {
    mockApi(studentRoutes({ "GET /courses/1/me/profile": { ...profile, personalized: false } }));
    renderApp("/courses/1/progress");
    expect(await screen.findByRole("link", { name: "Personalize your tutor" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "How answers should look" })).not.toBeInTheDocument();
  });
});
