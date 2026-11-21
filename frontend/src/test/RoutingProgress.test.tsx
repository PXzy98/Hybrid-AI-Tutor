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

describe("routing step details (V22 B19)", () => {
  const detailed = (stage: string, status: string, detail: string): Progress => ({ stage, status: status as Progress["status"], detail, duration_ms: 3, elapsed_ms: 10 });
  const events = [
    detailed("retrieval", "completed", "Retrieved 4 passages."),
    detailed("evidence", "skipped", "Capability/uncertainty gate did not pass."),
    detailed("decision", "completed", "CLOUD selected using LR."),
    detailed("web_search", "failed", "Web search failed; course material only."),
    detailed("embedding", "completed", "Local semantic vector ready."),
    detailed("classification", "completed", "Cloud need 19.2%; evidence required: True."),
  ];

  it("shows translated plain sentences and no technical English in French", () => {
    const t = trace(events);
    t.details = { target: "cloud", evidence: { status: "unavailable", coverage: 0 }, analysis: { label_origin: "prototype_policy" } } as never;
    const { container } = render(<I18nProvider lang="fr"><RoutingProgress trace={t} /></I18nProvider>);
    expect(screen.getByText("4 passages trouvés dans le matériel du cours.")).toBeInTheDocument();
    expect(screen.getByText("Modèle infonuagique choisi.")).toBeInTheDocument();
    expect(screen.getByText(/Preuves : indisponibles/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Retrieved|selected using|gate did not|vector ready|Cloud need|Web search|prototype/i);
  });

  it("hides a detail it does not know in French and shows it in English", () => {
    const unknown = trace([detailed("retrieval", "skipped", "Something new.")]);
    const fr = render(<I18nProvider lang="fr"><RoutingProgress trace={unknown} /></I18nProvider>);
    expect(fr.container.textContent).not.toContain("Something new.");
    fr.unmount();
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([detailed("embedding", "running", "Encoding the question locally.")])} /></I18nProvider>);
    expect(screen.getByText("Encoding the question locally.")).toBeInTheDocument();
  });

  it("reads the number of passages in English too", () => {
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([detailed("retrieval", "completed", "Retrieved 4 passages.")])} /></I18nProvider>);
    expect(screen.getByText("Found 4 passages in the course material.")).toBeInTheDocument();
  });
});
