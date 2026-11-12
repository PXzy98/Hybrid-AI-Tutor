import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { admin, type SurveySummary } from "../api/endpoints";
import { TRIAL_QUESTIONS } from "../components/surveyScenarios";
import SurveyPage from "../pages/admin/Survey";

const makeClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});
const mount = (component: React.ReactNode) =>
  render(<QueryClientProvider client={makeClient()}>{component}</QueryClientProvider>);

afterEach(() => vi.restoreAllMocks());

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
