import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { api, admin, type SurveySummary } from "../api/endpoints";
import FeedbackSurvey from "../components/FeedbackSurvey";
import { TRIAL_QUESTIONS } from "../components/surveyScenarios";
import SurveyPage from "../pages/admin/Survey";

const makeClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});
const mount = (component: React.ReactNode) =>
  render(<QueryClientProvider client={makeClient()}>{component}</QueryClientProvider>);

afterEach(() => vi.restoreAllMocks());

it("requires all four scores, sends only topic + ratings and confirms success", async () => {
  const post = vi.spyOn(api, "submitSurvey").mockResolvedValue({ saved: true });
  mount(<FeedbackSurvey topic="asthma" />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /Rate this answer/i }));
  const button = screen.getByRole("button", { name: "Submit feedback" });
  expect(button).toBeDisabled();
  for (const question of [
    /How helpful/i,
    /How relevant/i,
    /How easy/i,
    /How confident/i,
  ]) {
    await user.click(screen.getByRole("group", { name: question }).querySelectorAll('input')[4]);
  }
  expect(button).toBeEnabled();
  await user.click(button);
  await waitFor(() => expect(post).toHaveBeenCalled());
  expect(post.mock.calls[0][0]).toEqual({
    topic: "asthma", helpfulness: 5, material_relevance: 5,
    clarity: 5, source_confidence: 5,
  });
  expect(await screen.findByText(/anonymous ratings were saved/)).toBeInTheDocument();
});

it("can skip without an API call and lets users retry after a network error", async () => {
  const post = vi.spyOn(api, "submitSurvey").mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ saved: true });
  const user = userEvent.setup();
  const screen1 = mount(<FeedbackSurvey topic="migraine" />);
  await user.click(screen.getByRole("button", { name: /Rate this answer/i }));
  await user.click(screen.getByRole("button", { name: "Skip" }));
  expect(post).not.toHaveBeenCalled();
  screen1.unmount();

  mount(<FeedbackSurvey topic="asthma" />);
  await user.click(screen.getByRole("button", { name: /Rate this answer/i }));
  for (const question of [/How helpful/i, /How relevant/i, /How easy/i, /How confident/i]) {
    await user.click(screen.getByRole("group", { name: question }).querySelectorAll('input')[2]);
  }
  await user.click(screen.getByRole("button", { name: "Submit feedback" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");
  await user.click(screen.getByRole("button", { name: "Submit feedback" }));
  expect(await screen.findByText(/anonymous ratings were saved/)).toBeInTheDocument();
  expect(post).toHaveBeenCalledTimes(2);
});

it("shows aggregates only, and hides scores for small topics", async () => {
  const data: SurveySummary = { min_group_size: 3, topics: [
    { topic: "asthma", count: 3, sufficient_sample: true,
      mean_helpfulness: 4.33, mean_material_relevance: 4, mean_clarity: 3.67,
      mean_source_confidence: 4.67 },
    { topic: "migraine", count: 1, sufficient_sample: false,
      mean_helpfulness: null, mean_material_relevance: null, mean_clarity: null,
      mean_source_confidence: null },
  ] };
  const get = vi.spyOn(admin, "surveySummary").mockResolvedValue(data);
  mount(<SurveyPage />);
  expect(await screen.findByText("4.33")).toBeInTheDocument();
  expect(screen.getAllByText("Hidden")).toHaveLength(4);
  expect(screen.getByText(/Counts represent submissions/)).toBeInTheDocument();
  expect(screen.queryByText(/student.id/i)).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "Refresh summary" }));
  await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
});

it("defines one safe demo prompt for each of the five built-in topics", () => {
  expect(Object.keys(TRIAL_QUESTIONS)).toHaveLength(5);
  for (const question of Object.values(TRIAL_QUESTIONS)) {
    expect(question.length).toBeGreaterThan(20);
    expect(question).toMatch(/\?$/);
  }
});
