import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { COURSE, instructorRoutes, mockApi, reply, renderApp } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const routes = (extra = {}) => instructorRoutes({
  "GET /courses/1/settings": { values: { visibility_mode: "A", local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
  "GET /courses/1/model-endpoints": [],
  ...extra,
});
const NEW_COURSE = { ...COURSE, id: 2, code: "ECE 1000 W", title: "Fictional Circuits", term_label: "Winter", my_role: "instructor" };

const field = (id: string) => document.getElementById(id) as HTMLElement;

describe("start next term's course", () => {
  it("sends code, title and term, says students are not copied, and opens the new course", async () => {
    const calls = mockApi(routes({
      "POST /courses/1/copy": () => reply({ course: NEW_COURSE, copied: { modules: 1, kcs: 2, items: 3, misconceptions: 0, quizzes: 0, materials: 1 }, rebuild_job_id: 5 }, 201),
      "GET /courses/2": NEW_COURSE,
      "GET /courses": [{ ...COURSE, my_role: "instructor" }, NEW_COURSE],
    }));
    renderApp("/courses/1/settings");
    expect(await screen.findByText(/Students and their data are not copied/)).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(field("nt-code"), "ECE 1000 W");
    await user.type(field("nt-term"), "Winter");
    await user.click(screen.getByRole("button", { name: "Create the new course" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/copy")?.body).toEqual(
      { code: "ECE 1000 W", title: "Fictional Circuits", term_label: "Winter" }));
    expect(await screen.findByRole("heading", { name: /ECE 1000 W/ })).toBeInTheDocument();
  }, 15000);

  it("asks for another code when the code is taken", async () => {
    mockApi(routes({ "POST /courses/1/copy": () => reply({ detail: "a course with this code exists", code: "conflict" }, 409) }));
    renderApp("/courses/1/settings");
    await screen.findByText(/Students and their data are not copied/);
    const user = userEvent.setup();
    await user.type(field("nt-code"), "ECE 1000");
    await user.click(screen.getByRole("button", { name: "Create the new course" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose another code.");
  });
});
