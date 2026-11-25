import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider, tEnglish } from "../i18n";
import { readablePlaceholders } from "../lib/placeholders";
import Sources, { sourceTitle } from "../pages/student/chat/Sources";
import { instructorRoutes, mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("sources (Q1-06)", () => {
  it("drops the number prefix and capitalises a title taken from a file name", () => {
    expect(sourceTitle("01 lecture 1")).toBe("Lecture 1");
    expect(sourceTitle("02_circuit_basics")).toBe("Circuit basics");
    expect(sourceTitle("Kirchhoff's laws")).toBe("Kirchhoff's laws");
    expect(sourceTitle("10_intro")).toBe("Intro");
    expect(sourceTitle("12")).toBe("12");
  });

  it("keeps section numbers and numbers that are part of the title", () => {
    expect(sourceTitle("2.3 Kirchhoff's laws")).toBe("2.3 Kirchhoff's laws");
    expect(sourceTitle("3 phase power")).toBe("3 phase power");
    expect(sourceTitle("1.5 V cells")).toBe("1.5 V cells");
    expect(sourceTitle("2026 budget plan")).toBe("2026 budget plan");
  });

  it("shows the clean title and still the file it came from", () => {
    render(<I18nProvider lang="en"><Sources sources={[{ title: "01 lecture 1", source: "course/01_lecture_1.pdf", kc_ids: [] }]} /></I18nProvider>);
    expect(screen.getByText("Lecture 1")).toBeInTheDocument();
    expect(screen.getByText("01_lecture_1.pdf")).toHaveAttribute("title", "01_lecture_1.pdf");
  });
});

describe("placeholders in past turns (Q1-03 display)", () => {
  it("turns filter markers into neutral tokens in both languages", () => {
    expect(readablePlaceholders("What is <PERSON_1>'s law, asked by <EMAIL_ADDRESS_2>?", tEnglish)).toBe("What is [name]'s law, asked by [email address]?");
    expect(readablePlaceholders("<SOMETHING_NEW_3> here", tEnglish)).toBe("[removed] here");
    expect(readablePlaceholders("a < b and b > c", tEnglish)).toBe("a < b and b > c");
  });

  it("reads markers the model reformatted, and leaves code as written", () => {
    expect(readablePlaceholders("Ask <person_1> or [ PERSON_2 ].", tEnglish)).toBe("Ask [name] or [name].");
    expect(readablePlaceholders("Use a[i_1] here", tEnglish)).toBe("Use a[i_1] here");
    const code = "`template<N_1>` and\n```\nx = <T_1>\n```\n";
    expect(readablePlaceholders(`${code}by <PERSON_1>`, tEnglish)).toBe(`${code}by [name]`);
  });

  it("shows them in the stored conversation the student reopens", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/conversations": [{ conversation_id: "c-9", turns: 2, last_at: "2020-01-01T10:00:00Z" }],
      "GET /courses/1/conversations/c-9": { conversation_id: "c-9", turns: [
        { role: "student", text: "What is <PERSON_1>'s current law" }, { role: "tutor", text: "<PERSON_1>'s Current Law says more" }] },
    }));
    renderApp("/courses/1/chat?c=c-9", "fr");
    expect(await screen.findByText("What is [nom]'s current law")).toBeInTheDocument();
    expect(screen.getByText(/\[nom\]'s Current Law/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("<PERSON_1>");
  });
});

describe("first visit layout (Q1-04, Q1-07)", () => {
  it("shows no scope chip and no empty announcements box before the first question", async () => {
    mockApi(studentRoutes({ "GET /courses/1/announcements": [] }));
    renderApp("/courses/1/chat");
    expect(await screen.findByText("What would you like to understand today?")).toBeInTheDocument();
    expect(screen.queryByText("Asking about:")).not.toBeInTheDocument();
    expect(screen.queryByText(/not posted any announcements/)).not.toBeInTheDocument();
  });

  it("does not scroll to the end of an empty conversation", async () => {
    const scroll = vi.fn();
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scroll;
    try {
      mockApi(studentRoutes({ "GET /courses/1/announcements": [] }));
      renderApp("/courses/1/chat");
      expect(await screen.findByText("What would you like to understand today?")).toBeInTheDocument();
      expect(scroll).not.toHaveBeenCalled();
    } finally {
      Element.prototype.scrollIntoView = original;
    }
  });
});

describe("conversation list (Q1-08)", () => {
  it("lists recent conversations right under New chat, with a date and the message count", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/conversations": [{ conversation_id: "c-9", turns: 4, last_at: "2020-01-01T10:00:00Z" }],
    }));
    renderApp("/courses/1/chat");
    const history = await screen.findByRole("navigation", { name: "Conversations" });
    expect(within(history).getByRole("button")).toHaveTextContent("4 messages");
    const newChat = screen.getAllByRole("button", { name: "New chat" })[0];
    expect(newChat.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(history.compareDocumentPosition(screen.getAllByRole("navigation", { name: "Student dashboard" })[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("keeps the older conversations one click away", async () => {
    const rows = Array.from({ length: 10 }, (_, i) => ({ conversation_id: `c-${i}`, turns: i + 1, last_at: `2020-01-${String(20 - i).padStart(2, "0")}T10:00:00Z` }));
    mockApi(studentRoutes({ "GET /courses/1/conversations": rows }));
    renderApp("/courses/1/chat");
    const history = await screen.findByRole("navigation", { name: "Conversations" });
    expect(within(history).queryByText(/· 10 messages/)).not.toBeInTheDocument();
    await userEvent.setup().click(within(history).getByRole("button", { name: "Show all conversations (10)" }));
    expect(within(history).getByText(/· 10 messages/)).toBeInTheDocument();
    expect(within(history).getByRole("button", { name: "Show recent only" })).toHaveAttribute("aria-expanded", "true");
  });

  it("shows the whole list when an older conversation is open", async () => {
    const rows = Array.from({ length: 10 }, (_, i) => ({ conversation_id: `c-${i}`, turns: i + 1, last_at: `2020-01-${String(20 - i).padStart(2, "0")}T10:00:00Z` }));
    mockApi(studentRoutes({ "GET /courses/1/conversations": rows, "GET /courses/1/conversations/c-9": { conversation_id: "c-9", turns: [] } }));
    renderApp("/courses/1/chat?c=c-9");
    const history = await screen.findByRole("navigation", { name: "Conversations" });
    expect(await within(history).findByText(/· 10 messages/)).toBeInTheDocument();
  });
});

describe("course pages that are not there (Q1-10)", () => {
  it("shows a heading and a way back for a course the person cannot open", async () => {
    mockApi(studentRoutes());
    renderApp("/courses/99/chat");
    expect(await screen.findByText("Course not available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to My courses" })).toHaveAttribute("href", "/courses");
  });

  it("says so for an unknown page of a course instead of opening the chat", async () => {
    mockApi(studentRoutes());
    renderApp("/courses/1/nonexistent");
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
    // the chat stays mounted, hidden, so an answer that is still coming in is kept
    expect(screen.getByText("What would you like to understand today?")).not.toBeVisible();
    expect(screen.getByRole("link", { name: "Back to the course" })).toHaveAttribute("href", "/courses/1");
    expect(document.title).toMatch(/^Page not found · /);
  });

  it("does the same for an instructor", async () => {
    mockApi(instructorRoutes());
    renderApp("/courses/1/nonexistent");
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
  });
});

describe("My progress (Q1-13)", () => {
  it("has one My progress heading and a delete button that is not the filled destructive one", async () => {
    mockApi(studentRoutes());
    renderApp("/courses/1/progress");
    await screen.findByRole("button", { name: "Delete my learning data in this course" });
    expect(screen.getAllByRole("heading", { name: "My progress" })).toHaveLength(1);
    const button = screen.getByRole("button", { name: "Delete my learning data in this course" });
    expect(button.className).not.toContain("bg-destructive ");
    expect(button.className).toContain("text-destructive");
    await userEvent.setup().click(button);
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete my data" })).toBeInTheDocument());
  });
});
