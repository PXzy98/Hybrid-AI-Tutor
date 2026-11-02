import { useQuery } from "@tanstack/react-query";

import { admin } from "../../api/endpoints";
import type { SurveyTopicSummary } from "../../api/endpoints";
import { useI18n, type T } from "../../i18n";

const TOPIC_NAMES: Record<string, string> = {
  high_blood_pressure: "High Blood Pressure",
  type2_diabetes: "Type 2 Diabetes",
  asthma: "Asthma",
  migraine: "Migraine",
  pneumonia: "Pneumonia",
};

function score(t: T, value: number | null | undefined): string {
  return value == null ? t("fb.hidden") : value.toFixed(2);
}

function SurveyTopic({ item }: { item: SurveyTopicSummary }) {
  const { t } = useI18n();
  return (
    <tr className="border-t border-slate-200">
      <th scope="row" className="px-3 py-2 text-left font-medium">
        {TOPIC_NAMES[item.topic] ?? item.topic}
      </th>
      <td className="px-3 py-2 text-right">{item.count}</td>
      <td className="px-3 py-2 text-right">{score(t, item.mean_helpfulness)}</td>
      <td className="px-3 py-2 text-right">{score(t, item.mean_material_relevance)}</td>
      <td className="px-3 py-2 text-right">{score(t, item.mean_clarity)}</td>
      <td className="px-3 py-2 text-right">{score(t, item.mean_source_confidence)}</td>
    </tr>
  );
}

/** Only aggregate survey ratings; individual answers are never available to instructors. */
export default function SurveyPage() {
  const query = useQuery({ queryKey: ["survey-summary"], queryFn: admin.surveySummary });
  const { t } = useI18n();
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("fb.title")}</h2>
        <p className="text-sm text-slate-600">
          {t("fb.intro")}
        </p>
      </div>
      {query.isLoading && <p role="status">{t("fb.loading")}</p>}
      {query.isError && <p role="alert" className="text-rose-700">{t("fb.loadError")}</p>}
      {query.data && (
        <>
          <p className="text-sm text-amber-900">
            {t("fb.hiddenNote", { n: query.data.min_group_size })}
          </p>
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="w-full min-w-[720px] text-sm">
              <caption className="sr-only">{t("fb.caption")}</caption>
              <thead className="bg-slate-100 text-slate-800">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">{t("fb.col.topic")}</th>
                  <th scope="col" className="px-3 py-2 text-right">{t("fb.col.responses")}</th>
                  <th scope="col" className="px-3 py-2 text-right">{t("fb.col.helpful")}</th>
                  <th scope="col" className="px-3 py-2 text-right">{t("fb.col.materials")}</th>
                  <th scope="col" className="px-3 py-2 text-right">{t("fb.col.clarity")}</th>
                  <th scope="col" className="px-3 py-2 text-right">{t("fb.col.sources")}</th>
                </tr>
              </thead>
              <tbody>{query.data.topics.map((t) => <SurveyTopic key={t.topic} item={t} />)}</tbody>
            </table>
          </div>
          <button className="btn-secondary" type="button" onClick={() => query.refetch()}>
            {t("fb.refresh")}
          </button>
        </>
      )}
    </section>
  );
}
