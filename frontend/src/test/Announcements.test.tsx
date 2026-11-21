import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { instructorRoutes, mockApi, reply, renderApp, studentRoutes } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

// V20: course announcements. Fictional texts only.
const at = (day: string) => `2026-11-${day}T15:00:00Z`;
const note = (id: number, title: string, day: string, extra: Record<string, unknown> = {}) =>
  ({ id, title, body: `Details of ${title.toLowerCase()}.`, pinned: false, created_at: at(day), updated_at: at(day), ...extra });
const PINNED = note(3, "Final exam information", "10", { pinned: true, body: "The final exam is on December 14.\nBring your student card." });
const REVIEW = note(2, "Midterm review session", "18");
const DEADLINE = note(1, "Problem set 5 deadline moved", "05");
const OLDEST = note(4, "Welcome to the course", "02");

describe("announcements for students (V20)", () => {
  it("shows the latest ones on the course home, pinned first, with their date", async () => {
    mockApi(studentRoutes({ "GET /courses/1/announcements": [PINNED, REVIEW, DEADLINE, OLDEST] }));
    renderApp("/courses/1/chat");
    const region = await screen.findByRole("region", { name: "Announcements" });
    const titles = within(region).getAllByRole("heading", { level: 4 }).map((h) => h.textContent);
    expect(titles).toEqual(["Final exam informationPinned", "Midterm review session", "Problem set 5 deadline moved"]);
    expect(within(region).getByText(/December 14/).textContent).toBe("The final exam is on December 14.\nBring your student card.");
    expect(within(region).getAllByRole("time")[0]).toHaveAttribute("dateTime", PINNED.created_at);
    expect(within(region).queryByText("Welcome to the course")).not.toBeInTheDocument();
    expect(within(region).getByRole("link", { name: "See all 4" })).toHaveAttribute("href", "/courses/1/announcements");
  });

  it("says so on the course home when there are none", async () => {
    mockApi(studentRoutes({ "GET /courses/1/announcements": [] }));
    renderApp("/courses/1/chat");
    const region = await screen.findByRole("region", { name: "Announcements" });
    expect(region).toHaveTextContent("Your instructors have not posted any announcements yet.");
  });

  it("lists them all on their own page, without the instructor's buttons", async () => {
    mockApi(studentRoutes({ "GET /courses/1/announcements": [PINNED, OLDEST] }));
    renderApp("/courses/1/announcements", "fr");
    // the page's own list (the hidden chat home has its own copy, outside the accessibility tree)
    expect(await screen.findByRole("heading", { level: 3, name: "Welcome to the course" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /Final exam information/ })).toHaveTextContent("Épinglée");
    expect(screen.queryByRole("button", { name: /Modifier|Supprimer/ })).not.toBeInTheDocument();
  });
});

describe("announcements for instructors (V20)", () => {
  it("writes a new one in a dialog, says it was saved and returns focus", async () => {
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/announcements": [],
      "POST /courses/1/announcements": (c: { body: unknown }) => reply({ ...note(9, "Office hours", "21"), ...(c.body as object) }, 201),
    }));
    renderApp("/courses/1/announcements");
    const user = userEvent.setup();
    expect(await screen.findByText("No announcements yet")).toBeInTheDocument();
    const open = screen.getByRole("button", { name: "New announcement" });
    await user.click(open);
    const dialog = await screen.findByRole("dialog", { name: "New announcement" });
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeDisabled();  // a title is needed
    await user.type(within(dialog).getByLabelText("Title"), "Office hours");
    await user.type(within(dialog).getByLabelText("Text"), "Tuesdays at 14:00.");
    await user.click(within(dialog).getByLabelText("Pin to the top"));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ title: "Office hours", body: "Tuesdays at 14:00.", pinned: true });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(open).toHaveFocus();
  });

  it("shows the privacy refusal inside the dialog", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/announcements": [REVIEW],
      "PATCH /courses/1/announcements/2": () => reply({ detail: "the privacy scan found student data: STUDENT_ID", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/announcements");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit Midterm review session" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit the announcement" });
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Midterm review session");
    await user.type(within(dialog).getByLabelText("Text"), " Student 300000000 asked.");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("The privacy scan found student data (STUDENT_ID). Remove it and save again.");
    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
  });

  it("pins and deletes after a confirmation", async () => {
    let rows = [REVIEW, DEADLINE];
    const calls = mockApi(instructorRoutes({
      "GET /courses/1/announcements": () => rows,
      "PATCH /courses/1/announcements/1": () => ({ ...DEADLINE, pinned: true }),
      "DELETE /courses/1/announcements/2": () => { rows = rows.filter((r) => r.id !== 2); return reply(undefined, 204); },
    }));
    renderApp("/courses/1/announcements");
    const user = userEvent.setup();
    const pin = await screen.findByRole("button", { name: "Pin Problem set 5 deadline moved" });
    expect(pin).toHaveAttribute("aria-pressed", "false");
    await user.click(pin);
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ pinned: true }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete Midterm review session" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete this announcement?" });
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    expect(screen.getByRole("button", { name: "Delete Midterm review session" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Delete Midterm review session" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Midterm review session")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "New announcement" })).toHaveFocus();
  });
});
