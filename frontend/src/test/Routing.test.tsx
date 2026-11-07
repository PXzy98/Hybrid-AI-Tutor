import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { askStream, type RoutingEvent } from "../api/askStream";
import { api, type AskResponse } from "../api/endpoints";
import Chat from "../pages/Chat";
import Settings from "../pages/admin/Settings";

const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
const reply: AskResponse = { session_id: "session", answer: "A clear answer.", model_used: "local", route_target: "local",
  sources: [], checks: [], warnings: [], timings_ms: {}, routing_progress: [] };
const askDefaults = { session_id: "", course_id: "default", language: "en" };
const options = { show_progress: true, default_method: "lr", methods: [{ id: "lr", label: "Logistic Regression (LR)" }, { id: "svm", label: "Support Vector Machine (SVM)" }] };
function mount(element: JSX.Element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}
function stubChat(show = true) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("routing/options")) return json({ ...options, show_progress: show });
    if (url.endsWith("/topics")) return json([{ id: "high_blood_pressure", name: "High Blood Pressure" }, { id: "asthma", name: "Asthma" }]);
    if (url.endsWith("learner/me")) return json({ personalized: false });
    throw new Error(`Unexpected URL ${url}`);
  }));
}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("SSE client", () => {
  it("parses split UTF-8, CRLF frames, progress and a final result", async () => {
    const text = ': heartbeat\r\n\r\nevent: progress\r\ndata: {"stage":"embedding","status":"running","elapsed_ms":1}\r\n\r\n'
      + `event: result\r\ndata: ${JSON.stringify({ ...reply, answer: "回答正常" })}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n`;
    const bytes = new TextEncoder().encode(text);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream({ start(controller) {
      for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
      controller.close();
    } }))));
    const events: RoutingEvent[] = [];
    const result = await askStream({ ...askDefaults, topic: "asthma", question: "What is asthma?", routing_method: "svm" }, (e) => events.push(e));
    expect(result.answer).toBe("回答正常");
    expect(events.map((e) => e.type)).toEqual(["progress", "result"]);
  });
  it("reports an interrupted stream without inventing an answer", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response('event: progress\ndata: {"stage":"embedding","status":"running","elapsed_ms":1}\n\n')));
    await expect(askStream({ ...askDefaults, topic: "asthma", question: "Explain asthma" }, () => undefined)).rejects.toThrow("before an answer");
  });
  it("surfaces a server error event", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response('event: error\ndata: {"detail":"Cloud unavailable"}\n\n')));
    await expect(askStream({ ...askDefaults, topic: "asthma", question: "Explain asthma" }, () => undefined)).rejects.toThrow("Cloud unavailable");
  });
});

describe("Student routing controls", () => {
  it("sends the selected method and displays progress before the answer", async () => {
    stubChat();
    let finish!: (value: AskResponse) => void;
    const spy = vi.spyOn(api, "askStream").mockImplementation(async (_body, emit) => {
      emit({ type: "meta", data: { request_id: "r", session_id: "s", show_progress: true, method: "svm" } });
      emit({ type: "progress", data: { stage: "embedding", status: "running", elapsed_ms: 1, detail: "Encoding locally" } });
      return new Promise((resolve) => { finish = resolve; });
    });
    mount(<Chat />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByLabelText("Routing method")).toBeEnabled());
    await user.selectOptions(screen.getByLabelText("Routing method"), "svm");
    await user.type(screen.getByLabelText("Your question"), "Explain hypertension");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("region", { name: "Routing progress" })).toHaveTextContent("SVM");
    expect(screen.getByText("Semantic encoding")).toHaveTextContent("running");
    expect(screen.queryByText(reply.answer)).not.toBeInTheDocument();
    expect(spy.mock.calls[0][0].routing_method).toBe("svm");
    expect(screen.getByLabelText("Routing method")).toBeDisabled();
    await act(async () => finish(reply));
    expect(await screen.findByText(reply.answer)).toBeInTheDocument();
  });
  it("hides the box when the instructor disables it while retaining method selection", async () => {
    stubChat(false);
    vi.spyOn(api, "askStream").mockResolvedValue(reply);
    mount(<Chat />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Your question"), "Explain hypertension");
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(reply.answer)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Routing progress" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Routing method")).toBeInTheDocument();
  });
  it("keeps an in-flight answer in its original topic", async () => {
    stubChat();
    let finish!: (value: AskResponse) => void;
    vi.spyOn(api, "askStream").mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    mount(<Chat />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Your question"), "Explain hypertension");
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Send" }));
    await user.selectOptions(screen.getByLabelText("Topic"), "asthma");
    await act(async () => finish(reply));
    expect(screen.queryByText(reply.answer)).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Topic"), "high_blood_pressure");
    expect(screen.getByText(reply.answer)).toBeInTheDocument();
  });
});

it("saves the instructor progress-display setting", async () => {
  let values = { routing_threshold: 0.6, show_routing_progress: true, checkers: [], knowledge: "bkt", weak_evidence: false,
    levels: { basic_below: 0.4, advanced_above: 0.7, hysteresis: 0.05 } };
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "PUT") values = JSON.parse(init.body as string);
    return json({ values, options: { checkers: [], required_checkers: [], knowledge_models: ["bkt"] }, history: [] });
  });
  vi.stubGlobal("fetch", fetchMock);
  mount(<Settings />);
  const toggle = await screen.findByLabelText("Show routing progress and timings in the student chat");
  const user = userEvent.setup();
  await user.click(toggle);
  await user.click(screen.getByRole("button", { name: "Save and apply" }));
  await waitFor(() => expect(values.show_routing_progress).toBe(false));
});
