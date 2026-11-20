import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { COURSE, ME_STUDENT, mockApi, renderApp, studentRoutes } from "./helpers";

// v5 V3, with the deployment default of V1 (individual views off)
const STATS_ONLY = { ...COURSE, visibility_mode: "A" as const, individual_view: false };
const routes = () => studentRoutes({
  "GET /courses": [STATS_ONLY],
  "GET /courses/1/me/profile": { personalized: false, modules: [], visibility: { mode: "A", acknowledged: false, opted_out: false, visible_to_instructor: false, visible_since: null } },
});

// an in-memory storage per test (the runtime's own localStorage is not usable in the test environment)
beforeEach(() => {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k), clear: () => data.clear(), key: () => null, length: 0,
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("privacy notice", () => {
  it("opens in full on the first visit and stays a short line after Got it", async () => {
    mockApi(routes());
    const first = renderApp("/courses/1/progress");
    const notice = await screen.findByRole("region", { name: "Your privacy in this course" });
    expect(notice).toHaveTextContent("Your instructor sees class statistics only.");
    expect(notice).toHaveTextContent("No one, not even your instructor, can see them.");
    await userEvent.setup().click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(screen.queryByText(/No one, not even your instructor/)).not.toBeInTheDocument());
    first.unmount();

    renderApp("/courses/1/chat");
    const line = await screen.findByRole("region", { name: "Your privacy in this course" });
    expect(line).toHaveTextContent("Private: only you see your questions, answers and progress.");
    expect(screen.queryByText(/No one, not even your instructor/)).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "What is private?" }));
    expect(await screen.findByText(/No one, not even your instructor/)).toBeInTheDocument();
  });

  it("opens in full for another student on the same computer (V17 W22)", async () => {
    mockApi(routes());
    const first = renderApp("/courses/1/progress");
    await screen.findByRole("region", { name: "Your privacy in this course" });
    await userEvent.setup().click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(screen.queryByText(/No one, not even your instructor/)).not.toBeInTheDocument());
    first.unmount();

    mockApi({ ...routes(), "GET /auth/me": { ...ME_STUDENT, account_id: 99, username: "kim", display_name: "Kim Student" } });
    renderApp("/courses/1/progress");
    expect(await screen.findByText(/No one, not even your instructor/)).toBeInTheDocument();
  });

  it("is shown in French", async () => {
    mockApi(routes());
    renderApp("/courses/1/progress", "fr");
    const notice = await screen.findByRole("region", { name: "Votre vie privée dans ce cours" });
    expect(notice).toHaveTextContent("Personne, pas même votre enseignant, ne peut les voir.");
  });

  it("says progress may be shared when individual views are on", async () => {
    mockApi(studentRoutes({ "GET /courses": [{ ...COURSE, individual_view: true }] }));
    renderApp("/courses/1/progress");
    const notice = await screen.findByRole("region", { name: "Your privacy in this course" });
    expect(notice).toHaveTextContent("Your progress stays private unless you agree to share it on My progress.");
    expect(notice).not.toHaveTextContent("your progress are private");
  });

  it("opens in full for a course not visited yet after switching course", async () => {
    const other = { ...STATS_ONLY, id: 2, code: "ECE 2000", title: "Second fictional course" };
    mockApi({ ...routes(), "GET /courses": [STATS_ONLY, other],
      "GET /courses/2/me/profile": routes()["GET /courses/1/me/profile"] });
    renderApp("/courses/1/progress");
    const user = userEvent.setup();
    await screen.findByRole("region", { name: "Your privacy in this course" });
    await user.click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Got it" })).not.toBeInTheDocument());
    await user.selectOptions(screen.getByRole("combobox", { name: "Courses" }), "2");
    expect(await screen.findByRole("button", { name: "Got it" })).toBeInTheDocument();
  });

  it("is not shown to instructors", async () => {
    mockApi({ ...routes(), "GET /auth/me": { ...(await import("./helpers")).ME_INSTRUCTOR },
      "GET /courses": [{ ...STATS_ONLY, my_role: "instructor" }], "GET /courses/1/overview": { students: 0 } });
    renderApp("/courses/1/overview");
    await screen.findByRole("navigation", { name: /instructor/i });
    expect(screen.queryByRole("region", { name: "Your privacy in this course" })).not.toBeInTheDocument();
  });
});
