import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CheckItem } from "../api/endpoints";
import CheckCard from "../components/CheckCard";

const ITEM: CheckItem = {
  id: "HBP.1-q3",
  kc_id: "HBP.1",
  stem: "Why is high blood pressure often called a 'silent' condition?",
  options: { B: "It only matters in older adults", A: "It can only be measured while asleep",
             D: "It always causes headaches", C: "It often causes no noticeable symptoms" },
};

function renderCard() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CheckCard item={ITEM} sessionId="s-1" />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("CheckCard", () => {
  it("renders the four options in order, without any answer key", () => {
    renderCard();
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => (r as HTMLInputElement).value)).toEqual(["A", "B", "C", "D"]);
    expect(screen.queryByText(/correct/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/answer is/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check answer" })).toBeDisabled();
  });

  it("submits the chosen option and shows the server's verdict", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        correct: false, correct_choice: "C", explanation: "Many people feel well.", kc_id: "HBP.1",
        kc_level: "basic", kc_band: "basic", next_kc: { kc_id: "HBP.1", name: "What blood pressure numbers mean", reason: "r" },
      }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByLabelText(/It always causes headaches/));
    await user.click(screen.getByRole("button", { name: "Check answer" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/check");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ item_id: "HBP.1-q3", choice: "D", session_id: "s-1" });

    expect(await screen.findByText("Not quite. The answer is C.")).toBeInTheDocument();
    expect(screen.getByText("Many people feel well.")).toBeInTheDocument();
    expect(screen.getByText(/What blood pressure numbers mean/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check answer" })).not.toBeInTheDocument();
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
  });
});
