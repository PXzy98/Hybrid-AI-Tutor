import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import WhatIKnow from "../pages/WhatIKnow";

const PROFILE = {
  personalized: true,
  preferences: { sequencing: "example_first", detail: "concise", source: "default" },
  topics: [{
    topic: "high_blood_pressure",
    name: "High Blood Pressure",
    kcs: [{ kc_id: "HBP.1", name: "What blood pressure numbers mean", band: "basic" }],
    misconceptions: [{
      kc_id: "HBP.1",
      statement: "Only the top number of a blood pressure reading matters.",
      correction: "Both numbers matter.",
      status: "confirmed",
    }],
  }],
};

afterEach(() => vi.unstubAllGlobals());

describe("WhatIKnow", () => {
  it("lists open misconceptions in plain language with their corrections, without IDs or numbers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(PROFILE), { status: 200, headers: { "Content-Type": "application/json" } }),
    ));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><WhatIKnow /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Ideas we are working on")).toBeInTheDocument();
    expect(screen.getByText(/Only the top number of a blood pressure reading matters\./)).toBeInTheDocument();
    expect(screen.getByText(/Both numbers matter\./)).toBeInTheDocument();
    expect(screen.getByText("(seen in your answers)")).toBeInTheDocument();
    expect(screen.queryByText(/MC\d/)).not.toBeInTheDocument();
  });
});
