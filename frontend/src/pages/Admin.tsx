import { Link } from "react-router-dom";

/** Instructor home. The full dashboard (students, class summary, settings, logs) is Step 13 (Beta). */
export default function Admin() {
  return (
    <div className="card mx-auto max-w-2xl space-y-3">
      <h1 className="text-xl font-semibold">Instructor dashboard</h1>
      <Link className="btn-primary inline-block" to="/admin/settings">Routing and tutor settings</Link>
      <p className="text-sm text-slate-700">
        Routing settings are available now. The full student-account and class-summary dashboard is planned for the Beta.
      </p>
      <p className="text-sm text-slate-700">
        Until then, create and manage student accounts through the API (<code>/api/v1/admin/students</code>), for
        example from the backend's interactive documentation at <code>http://localhost:8000/docs</code>.
      </p>
    </div>
  );
}
