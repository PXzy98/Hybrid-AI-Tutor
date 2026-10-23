import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import Settings from "../pages/admin/Settings";

const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><Settings /></MemoryRouter></QueryClientProvider>);
}

it("tests and saves the professor's local model server (G1-94)", async () => {
  let values = { routing_threshold: 0.6, show_routing_progress: true, checkers: [], knowledge: "bkt", weak_evidence: false,
    levels: { basic_below: 0.4, advanced_above: 0.7, hysteresis: 0.05 },
    local_llm_url: "http://192.168.2.25:11434", local_llm_model: "qwen3.5:9b" };
  const tested: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("llm-server/test")) {
      tested.push(JSON.parse(init?.body as string));
      return json({ reachable: true, model_available: false, models: ["llama3.1:8b"], latency_ms: 12,
        error: "the server does not have the model gemma4:e4b" });
    }
    if (init?.method === "PUT") values = JSON.parse(init.body as string);
    return json({ values, options: { checkers: [], required_checkers: [], knowledge_models: ["bkt"] }, history: [] });
  }));
  mount();
  const user = userEvent.setup();
  const address = await screen.findByLabelText("Server address");
  await user.clear(address);
  await user.type(address, "http://10.0.0.5:11434");
  const model = screen.getByLabelText("Model");
  await user.clear(model);
  await user.type(model, "gemma4:e4b");
  await user.click(screen.getByRole("button", { name: "Test connection" }));
  expect(await screen.findByText(/does not have the model gemma4:e4b/)).toBeInTheDocument();
  expect(screen.getByText(/Models on this server: llama3.1:8b/)).toBeInTheDocument();
  expect(tested).toEqual([{ url: "http://10.0.0.5:11434", model: "gemma4:e4b" }]);
  await user.click(screen.getByRole("button", { name: "Save and apply" }));
  await waitFor(() => expect(values.local_llm_url).toBe("http://10.0.0.5:11434"));
  expect(values.local_llm_model).toBe("gemma4:e4b");
});
