import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

// V18: the wording of a KC and of a check item can be edited; the code, the module and the answer stay.
const KC = { id: 5, module_id: 10, code: "K1", name: "Resistance", definition: "How a part resists current.", difficulty: "basic", status: "active", prerequisite_ids: [] };
const ITEM = { id: 8, kc_id: 5, code: "K1-q1", level: "basic", stem: "What is resistance measured in?", answer: "B", explanation: "The unit is the ohm.", status: "active",
  options: { A: { text: "Volts", misconception: "MC1" }, B: { text: "Ohms", misconception: null }, C: { text: "Amperes", misconception: null }, D: { text: "Watts", misconception: null } } };

const contentRoutes = (extra: Record<string, unknown> = {}) => instructorRoutes({
  "GET /courses/1/kcs": [KC],
  "GET /courses/1/check-items": [ITEM],
  "GET /courses/1/misconceptions": [],
  ...extra,
});

describe("editing the wording of content (V18)", () => {
  it("renames a knowledge component and says it was saved", async () => {
    const calls = mockApi(contentRoutes({ "PATCH /courses/1/kcs/5": { ...KC, name: "Electrical resistance" } }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit Resistance" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("To change what it means, retire it and add a new one.");
    const name = within(dialog).getByLabelText("Name");
    expect(name).toHaveValue("Resistance");
    await user.clear(name);
    await user.type(name, "Electrical resistance");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ name: "Electrical resistance", definition: "How a part resists current." });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  }, 15000); // the first test also loads the lazy Content page chunk

  it("rewords a check item and keeps its answer and misconception tags", async () => {
    const calls = mockApi(contentRoutes({ "PATCH /courses/1/check-items/8": { ...ITEM, stem: "Which unit measures resistance?" } }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit K1-q1" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Option B (correct answer)")).toHaveValue("Ohms");
    const stem = within(dialog).getByLabelText("Question");
    await user.clear(stem);
    await user.type(stem, "Which unit measures resistance?");
    await user.clear(within(dialog).getByLabelText("Option D"));
    await user.type(within(dialog).getByLabelText("Option D"), "Joules");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({
      stem: "Which unit measures resistance?", explanation: "The unit is the ohm.",
      options: { A: { text: "Volts", misconception: "MC1" }, B: { text: "Ohms", misconception: null },
        C: { text: "Amperes", misconception: null }, D: { text: "Joules", misconception: null } },
    });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("cannot save an empty option and shows the server's refusal", async () => {
    mockApi(contentRoutes({
      "PATCH /courses/1/kcs/5": () => reply({ detail: "another active KC of this course has this name", code: "conflict" }, 409),
    }));
    renderApp("/courses/1/content");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit K1-q1" }));
    let dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Option A"));
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeDisabled();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Edit Resistance" }));
    dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), " 2");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/another active KC of this course has this name/i);
    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
  });

  it("shows the French editor", async () => {
    mockApi(contentRoutes());
    renderApp("/courses/1/content", "fr");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Modifier K1-q1" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Option B (bonne réponse)")).toHaveValue("Ohms");
    expect(dialog).toHaveTextContent("Pour en changer le sens, retirez-la et ajoutez-en une nouvelle.");
  });
});
