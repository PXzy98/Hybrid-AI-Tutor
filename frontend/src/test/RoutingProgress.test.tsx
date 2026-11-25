import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { RoutingProgress as Progress } from "../api/askStream";
import RoutingProgress, { keptLocalByPrivacy, type RoutingTrace } from "../components/RoutingProgress";
import { I18nProvider } from "../i18n";

const event = (stage: string): Progress => ({ stage, status: "completed", detail: "", duration_ms: 3, elapsed_ms: 10 });
const trace = (events: Progress[]): RoutingTrace =>
  ({ id: "t", method: "lr", visible: true, events, running: false, startedAt: 0, finishedAt: 20 });

describe("routing steps", () => {
  it("shows the web search step only when it ran", () => {
    const { unmount } = render(<I18nProvider lang="en"><RoutingProgress trace={trace([event("decision")])} /></I18nProvider>);
    expect(screen.getByText("Chose which model answers")).toBeInTheDocument();
    expect(screen.queryByText("Searched the allowed websites")).not.toBeInTheDocument();
    unmount();
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([event("decision"), event("web_search")])} /></I18nProvider>);
    expect(screen.getByText("Searched the allowed websites")).toBeInTheDocument();
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

  it("shows translated plain sentences and no technical English in French", async () => {
    const t = trace(events);
    t.details = { target: "cloud", evidence: { status: "unavailable", coverage: 0 }, analysis: { label_origin: "prototype_policy" } } as never;
    const { container } = render(<I18nProvider lang="fr"><RoutingProgress trace={t} /></I18nProvider>);
    expect(screen.getByText("4 passages trouvés dans le matériel du cours.")).toBeInTheDocument();
    expect(screen.getByText("Modèle infonuagique choisi.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Retrieved|selected using|gate did not|vector ready|Cloud need|Web search|prototype/i);
    // the technical values are inside the collapsed Details
    expect(screen.queryByText(/Preuves : indisponibles/)).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Détails" }));
    expect(screen.getByText(/Preuves : indisponibles/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Retrieved|selected using|gate did not|vector ready|Cloud need|Web search|prototype/i);
  });

  it("hides a detail it does not know in French and shows it in English, in the Details only", async () => {
    const unknown = trace([detailed("retrieval", "skipped", "Something new.")]);
    const fr = render(<I18nProvider lang="fr"><RoutingProgress trace={unknown} /></I18nProvider>);
    expect(fr.container.textContent).not.toContain("Something new.");
    fr.unmount();
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([detailed("embedding", "running", "Encoding the question locally.")])} /></I18nProvider>);
    expect(screen.queryByText("Encoding the question locally.")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Details" }));
    expect(screen.getByText("Encoding the question locally.")).toBeInTheDocument();
  });

  it("reads the number of passages in English too", () => {
    render(<I18nProvider lang="en"><RoutingProgress trace={trace([detailed("retrieval", "completed", "Retrieved 4 passages.")])} /></I18nProvider>);
    expect(screen.getByText("Found 4 passages in the course material.")).toBeInTheDocument();
  });
});

describe("one passage (retest N5)", () => {
  it("says 1 passage, not 1 passages", () => {
    const one = (stage: string, detail: string): Progress => ({ stage, status: "completed", detail, duration_ms: 3, elapsed_ms: 10 });
    render(<I18nProvider lang="fr"><RoutingProgress trace={trace([one("retrieval", "Retrieved 1 passages."), one("web_search", "Added 1 web passages.")])} /></I18nProvider>);
    expect(screen.getByText("1 passage trouvé dans le matériel du cours.")).toBeInTheDocument();
    expect(screen.getByText("1 passage du web ajouté.")).toBeInTheDocument();
  });
});

describe("privacy check kept the question local (X3)", () => {
  const cloud = { target: "cloud" } as never;
  const withDecision = (kept: boolean) => ({ ...trace([event("decision")]), details: cloud, privacyKeptLocal: kept });

  it("ends the panel with a step saying the privacy check kept it local, in English and French", () => {
    const en = render(<I18nProvider lang="en"><RoutingProgress trace={withDecision(true)} /></I18nProvider>);
    expect(en.container.querySelector("ol > li:last-child"))
      .toHaveTextContent("A privacy check kept this question on the local model, so the local model answered.");
    en.unmount();
    const fr = render(<I18nProvider lang="fr"><RoutingProgress trace={withDecision(true)} /></I18nProvider>);
    expect(fr.container.querySelector("ol > li:last-child")).toHaveTextContent("a gardé cette question sur le modèle local");
  });

  it("leaves a normal cloud answer unchanged", () => {
    const { container } = render(<I18nProvider lang="en"><RoutingProgress trace={withDecision(false)} /></I18nProvider>);
    expect(container).not.toHaveTextContent("privacy check kept");
    expect(container.querySelector("ol > li:last-child")).toHaveTextContent("Checked the answer");
  });

  it("detects the override from the answer notice, only for a cloud route", () => {
    const en = ["A privacy check kept this question on the local model."];
    const fr = ["Une vérification de confidentialité a gardé cette question sur le modèle local."];
    expect(keptLocalByPrivacy(cloud, en)).toBe(true);
    expect(keptLocalByPrivacy(cloud, fr)).toBe(true);
    expect(keptLocalByPrivacy(cloud, ["No cloud model is connected, so the local model answered this question."])).toBe(false);
    expect(keptLocalByPrivacy({ target: "local" } as never, en)).toBe(false);
  });
});

describe("plain default view (Q1-01)", () => {
  const timed = (stage: string, detail: string, duration_ms: number): Progress => ({ stage, status: "completed", detail, duration_ms, elapsed_ms: 10 });
  const full = () => {
    const t = trace([timed("retrieval", "Retrieved 4 passages.", 0), timed("evidence", "x", 0), timed("decision", "LOCAL selected using LR.", 1200)]);
    t.details = { target: "local", analysis: { cloud_probability: 0.043, label_origin: "prototype_policy" }, evidence: { status: "not_required", coverage: 0 } } as never;
    return t;
  };

  it("shows plain steps, and the method, percentages and timings only after opening Details", async () => {
    const { container } = render(<I18nProvider lang="en"><RoutingProgress trace={full()} /></I18nProvider>);
    expect(screen.getByText("Found 4 passages in the course material.")).toBeInTheDocument();
    expect(screen.getByText(/Answered by the course's own model/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\bLR\b|LOCAL|Estimated|coverage|0\.000 s|still being evaluated/);
    await userEvent.setup().click(screen.getByRole("button", { name: "Details" }));
    expect(container).toHaveTextContent("Routing · LR");
    expect(container).toHaveTextContent("Model: Local model");
    expect(container).toHaveTextContent("Estimated cloud need: 4.3%");
    expect(container).toHaveTextContent("1.200 s");
    expect(container.textContent).not.toMatch(/0\.000 s|still being evaluated/);
  });
});
