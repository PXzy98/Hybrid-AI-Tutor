import { useQuery } from "@tanstack/react-query";
import { useId } from "react";

import { api } from "../api/endpoints";

export default function TopicPicker({ value, onChange }: { value: string; onChange: (topic: string) => void }) {
  const id = useId();
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics });
  return (
    <div>
      <label htmlFor={id} className="label">Topic</label>
      <select id={id} className="input min-w-56" value={value} onChange={(e) => onChange(e.target.value)}>
        {(topics.data ?? [{ id: value, name: "Loading…", kc_count: 0, reviewed_item_count: 0 }]).map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
    </div>
  );
}
