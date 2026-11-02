import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useI18n } from "../i18n";

import ClassSummaryPage from "./admin/ClassSummary";
import ContentPage from "./admin/Content";
import LogsPage from "./admin/Logs";
import SettingsPage from "./admin/Settings";
import SurveyPage from "./admin/Survey";
import StudentsPage from "./admin/Students";

const TABS = ["students", "summary", "settings", "logs", "content", "survey"] as const;

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-t-md border-b-2 px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
    isActive ? "border-teal-700 text-teal-900" : "border-transparent text-slate-600 hover:text-slate-900"
  }`;

/** Instructor dashboard (design §3, §8.3): student accounts, aggregates, settings, logs, content. */
export default function Admin() {
  const { t } = useI18n();
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">{t("admin.title")}</h1>
        <p className="text-sm text-slate-600">{t("admin.intro")}</p>
      </div>
      <nav aria-label={t("admin.nav")} className="flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((tab) => <NavLink key={tab} to={tab} className={tabClass}>{t(`admin.tab.${tab}`)}</NavLink>)}
      </nav>
      <Routes>
        <Route index element={<Navigate to="students" replace />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="summary" element={<ClassSummaryPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="content" element={<ContentPage />} />
        <Route path="survey" element={<SurveyPage />} />
        <Route path="*" element={<Navigate to="students" replace />} />
      </Routes>
    </div>
  );
}
