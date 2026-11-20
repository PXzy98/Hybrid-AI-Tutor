import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderApp, studentRoutes } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const sse = (...frames: [string, unknown][]) =>
  new Response(frames.map(([k, d]) => `event: ${k}\ndata: ${JSON.stringify(d)}\n\n`).join(""), { headers: { "Content-Type": "text/event-stream" } });

// v5: the backend's fixed texts (consent, preference questions, chat notes) come in the interface language
describe("the interface language reaches the backend", () => {
  it("asks for the onboarding texts in French", async () => {
    const calls = mockApi(studentRoutes({
      "GET /courses/1/onboarding": { module_id: 10, consent_text: "Pour adapter les explications à vous…", consent_given: null,
        preference_questions: [], diagnostic: [] },
    }));
    renderApp("/courses/1/start?module=10", "fr");
    expect(await screen.findByText("Pour adapter les explications à vous…")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/courses/1/onboarding")!.query.get("language")).toBe("fr");
  });

  it("sends the chat question with the interface language", async () => {
    const answer = { session_id: "c-1", conversation_id: "c-1", answer: "Réponse.", model_used: "local-model", route_target: "local",
      sources: [], checks: [], warnings: ["Ce cours utilise seulement le modèle local."], timings_ms: {}, routing_progress: [], routing_details: null };
    const calls = mockApi(studentRoutes({
      "POST /courses/1/ask/stream": () => sse(["meta", { request_id: "r", conversation_id: "c-1", show_progress: false, method: "lr" }],
        ["result", answer], ["done", {}]),
    }));
    renderApp("/courses/1/chat?module=10", "fr");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Votre question"), "Qu’est-ce que la loi d’Ohm ?");
    await user.click(screen.getByRole("button", { name: "Envoyer" }));
    expect(await screen.findByText("Ce cours utilise seulement le modèle local.")).toBeInTheDocument();
    await waitFor(() => expect(calls.find((c) => c.path === "/courses/1/ask/stream")?.body).toMatchObject({ language: "fr" }));
  });
});
