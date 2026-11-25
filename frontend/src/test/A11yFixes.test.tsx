import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AskResponse } from "../api/endpoints";
import { PageHeader } from "../components/common";
import { Table } from "../components/ui/table";
import { I18nProvider } from "../i18n";
import { documentTitle } from "../lib/useDocumentTitle";
import MessageList, { type Message } from "../pages/student/chat/MessageList";
import { mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

describe("document title", () => {
  it("joins the page, the course code and the product name without repeating it", () => {
    expect(documentTitle("Chat", "ECE 1000")).toBe("Chat · ECE 1000 · ScholarMind AI");
    expect(documentTitle("My courses")).toBe("My courses · ScholarMind AI");
    expect(documentTitle("ScholarMind AI")).toBe("ScholarMind AI");
    expect(documentTitle()).toBe("ScholarMind AI");
  });

  it("follows the page: login, course picker, course section", async () => {
    mockApi({ "GET /auth/me": { detail: "no", code: "unauthenticated" } });
    const login = renderApp("/login");
    await screen.findByRole("heading", { level: 1 });
    expect(document.title).toBe("Log in · ScholarMind AI");
    login.unmount();

    mockApi(studentRoutes());
    const picker = renderApp("/courses");
    await screen.findByRole("heading", { level: 1, name: "My courses" });
    expect(document.title).toBe("My courses · ScholarMind AI");
    picker.unmount();

    renderApp("/courses/1/quizzes");
    // the course page is loaded on demand (T16); under a full parallel run that can take over a second
    await vi.waitFor(() => expect(document.title).toBe("Quizzes · ECE 1000 · ScholarMind AI"), { timeout: 5000 });
  });

  it("a section header mounted later keeps the course page's title", () => {
    document.title = "Start · ECE 1000 · ScholarMind AI";
    const section = render(<PageHeader title="Modules" />);
    expect(document.title).toBe("Start · ECE 1000 · ScholarMind AI");
    section.unmount();
    render(<PageHeader title="My courses" level={1} />);
    expect(document.title).toBe("My courses · ScholarMind AI");
  });
});

describe("scrollable table", () => {
  it("is keyboard focusable and a named region when it has a label", async () => {
    render(<Table label="Scores"><tbody><tr><td>1</td></tr></tbody></Table>);
    const region = screen.getByRole("region", { name: "Scores" });
    expect(region).toHaveAttribute("tabindex", "0");
    await userEvent.setup().tab();
    expect(region).toHaveFocus();
  });

  it("stays focusable without a label and then is not a region", () => {
    const { container } = render(<Table><tbody><tr><td>1</td></tr></tbody></Table>);
    expect(screen.queryByRole("region")).toBeNull();
    expect(container.firstElementChild).toHaveAttribute("tabindex", "0");
  });
});

describe("conversation announcements", () => {
  const reply = { answer: "Hello", route_target: "local", conversation_id: "c", warnings: [], sources: [] } as unknown as AskResponse;
  const list = (messages: Message[], pending = false) => (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter><I18nProvider lang="en">
        <MessageList courseId={1} messages={messages} partial="" pending={pending} loadingHistory={false} historyError={null}
                     onSuggest={() => undefined} onRetry={() => undefined}><div /></MessageList>
      </I18nProvider></MemoryRouter>
    </QueryClientProvider>
  );

  it("is not a live region itself and announces once when the answer is ready", () => {
    const sent: Message[] = [{ role: "student", text: "Q" }];
    const { container, rerender } = render(list(sent, true));
    expect(screen.getByRole("region", { name: "Conversation" })).not.toHaveAttribute("aria-live");
    const status = () => container.querySelector('[role="status"][aria-live="polite"]') as HTMLElement;
    expect(status()).toHaveTextContent("");
    rerender(list([...sent, { role: "tutor", reply }], false));
    expect(status()).toHaveTextContent("Answer ready");
    // the same answer rendered again does not add another live region
    rerender(list([...sent, { role: "tutor", reply }], false));
    expect(container.querySelectorAll('[aria-live="polite"]')).toHaveLength(1);
  });
});
