import { useQuery } from "@tanstack/react-query";
import { useId } from "react";

import { api } from "../api/endpoints";
import { useI18n } from "../i18n";

export default function TopicPicker({ value, onChange }: { value: string; onChange: (topic: string) => void }) {
  const id = useId();
  const { t } = useI18n();
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics });
  return (
    <div>
      <label htmlFor={id} className="label">{t("topic.label")}</label>
      <select id={id} className="input min-w-56" value={value} onChange={(e) => onChange(e.target.value)}>
        {(topics.data ?? [{ id: value, name: t("app.loading"), kc_count: 0, reviewed_item_count: 0 }]).map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
    </div>
  );
}
