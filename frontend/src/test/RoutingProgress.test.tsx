import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RoutingProgress as Progress } from "../api/askStream";
import RoutingProgress, { type RoutingTrace } from "../components/RoutingProgress";
import { I18nProvider } from "../i18n";

const event = (stage: string): Progress => ({ stage, status: "completed", detail: "", duration_ms: 3, elapsed_ms: 10 });
const trace = (events: Progress[]): RoutingTrace =>
  ({ id: "t", method: "lr", visible: true, events, running: false, startedAt: 0, finishedAt: 20 });

describe("routing steps", () => {
  it("shows the web search step only when it ran", () => {
    const { unmount } = render(<I18nProvider lang="en"><RoutingProgress trace={trace([event("decision")])} /></I18nProvider>);
    expect(screen.getByText("Local / Cloud decision")).toBeInTheDocument();
    expect(screen.queryByText("Web search on allowed sites")).not.toBeInTheDocument();
    unmount();
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([event("decision"), event("web_search")])} /></I18nProvider>);
    expect(screen.getByText("Web search on allowed sites")).toBeInTheDocument();
  });
});
