import { useQuery } from "@tanstack/react-query";

import { admin } from "../../api/endpoints";
import type { SurveyTopicSummary } from "../../api/endpoints";

const TOPIC_NAMES: Record<string, string> = {
  high_blood_pressure: "High Blood Pressure",
  type2_diabetes: "Type 2 Diabetes",
  asthma: "Asthma",
  migraine: "Migraine",
  pneumonia: "Pneumonia",
};

function score(value: number | null | undefined): string {
  return value == null ? "Hidden" : value.toFixed(2);
}

function SurveyTopic({ item }: { item: SurveyTopicSummary }) {
  return (
    <tr className="border-t border-slate-200">
      <th scope="row" className="px-3 py-2 text-left font-medium">
        {TOPIC_NAMES[item.topic] ?? item.topic}
      </th>
      <td className="px-3 py-2 text-right">{item.count}</td>
      <td className="px-3 py-2 text-right">{score(item.mean_helpfulness)}</td>
      <td className="px-3 py-2 text-right">{score(item.mean_material_relevance)}</td>
      <td className="px-3 py-2 text-right">{score(item.mean_clarity)}</td>
      <td className="px-3 py-2 text-right">{score(item.mean_source_confidence)}</td>
    </tr>
  );
}

/** Only aggregate survey ratings; individual answers are never available to instructors. */
export default function SurveyPage() {
  const query = useQuery({ queryKey: ["survey-summary"], queryFn: admin.surveySummary });
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Student feedback summary</h2>
        <p className="text-sm text-slate-600">
          Anonymous, voluntary 1–5 ratings about recent tutor answers.
          Counts represent submissions, not unique respondents.
        </p>
      </div>
      {query.isLoading && <p role="status">Loading feedback summary...</p>}
      {query.isError && <p role="alert" className="text-rose-700">Could not load feedback summary.</p>}
      {query.data && (
        <>
          <p className="text-sm text-amber-900">
            Scores are hidden until a topic has at least {query.data.min_group_size} submissions.
            Small groups and zero-submission topics display no individual scores.
          </p>
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="w-full min-w-[720px] text-sm">
              <caption className="sr-only">Aggregated voluntary student feedback by topic</caption>
              <thead className="bg-slate-100 text-slate-800">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">Topic</th>
                  <th scope="col" className="px-3 py-2 text-right">Responses</th>
                  <th scope="col" className="px-3 py-2 text-right">Helpful</th>
                  <th scope="col" className="px-3 py-2 text-right">Materials</th>
                  <th scope="col" className="px-3 py-2 text-right">Clarity</th>
                  <th scope="col" className="px-3 py-2 text-right">Sources</th>
                </tr>
              </thead>
              <tbody>{query.data.topics.map((t) => <SurveyTopic key={t.topic} item={t} />)}</tbody>
            </table>
          </div>
          <button className="btn-secondary" type="button" onClick={() => query.refetch()}>
            Refresh summary
          </button>
        </>
      )}
    </section>
  );
}
