import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { formatDate, formatDay } from "../lib/format";
import { sentences } from "../pages/student/Start";
import { COURSE, instructorRoutes, mockApi, ME_INSTRUCTOR, ME_STUDENT, renderApp, reply, studentRoutes } from "./helpers";

// v6 quality walk-through, instructor and admin pages (Q1-09 to Q1-26)

const STATS = { min_group: 5, students_enrolled: 8, active_students: 6, active_students_7d: 6, questions_total: 9, questions_7d: 4, local_share: 1,
  weeks: [], modules: [], quizzes: [] };
const OVERVIEW_ROUTES = {
  "GET /courses/1/statistics": STATS,
  "GET /courses/1/insights": { min_group: 5, suppressed: true, kc_question_counts: [], misconception_counts: [] },
  "GET /courses/1/weak-topics": { min_group: 5, topics: [] },
};

describe("dates (Q1-16)", () => {
  it("are spelled out in both languages, never as ISO digits", () => {
    for (const lang of ["en", "fr"] as const) {
      expect(formatDate("2026-11-16T15:00:00Z", lang)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
      expect(formatDay("2026-11-16", lang)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    }
    expect(formatDay("2026-11-16", "fr")).toMatch(/nov/);
  });
});

describe("quizzes and sidebar names (Q1-14, Q1-15)", () => {
  it("says there are no quizzes once", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/quizzes": [] }));
    renderApp("/courses/1/quizzes");
    expect(await screen.findByText("No quizzes yet")).toBeInTheDocument();
    expect(screen.queryByText("No quizzes yet.")).toBeNull();
  });

  it("names the two end-of-term entries differently and gives End of term a heading", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/settings": { values: {}, version: 1 },
    }));
    renderApp("/courses/1/endterm");
    expect(await screen.findByRole("heading", { name: "End of term", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "End-of-term survey" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "End term / next term" })).toBeInTheDocument();
  });
});

describe("class overview (Q1-16)", () => {
  it("shows no module picker without modules, and an empty state instead of empty lists", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/modules": [],
      ...OVERVIEW_ROUTES,
      "GET /courses/1/statistics": { ...STATS, weeks: [{ week_start: "2026-11-02", questions: 0, students: 0 }],
        modules: [{ module_id: null, title: "", questions: 0 }] },
    }));
    renderApp("/courses/1/overview");
    await screen.findByText("Questions per week");
    expect(screen.queryByLabelText("Module for the topic levels below")).toBeNull();
    expect(screen.getAllByText("No activity yet.")).toHaveLength(2);
    expect(screen.queryByText(/Week of/)).toBeNull();
  });

  it("collapses the modules nobody asked about and never writes a hidden student count as 0", async () => {
    mockApi(instructorRoutes({
      ...OVERVIEW_ROUTES,
      "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true },
      "GET /courses/1/statistics": { ...STATS,
        weeks: [{ week_start: "2026-11-02", questions: 7, students: null }, { week_start: "2026-11-09", questions: 0, students: 0 }],
        modules: [{ module_id: 10, title: "Ohm's law", questions: 3 }, { module_id: 11, title: "Quiet module", questions: 0 }] },
    }));
    renderApp("/courses/1/overview");
    expect(await screen.findByText("7 questions, students hidden")).toBeInTheDocument();
    expect(screen.queryByText(/0 students/)).toBeNull();
    expect(screen.getAllByText("Ohm's law").length).toBeGreaterThan(0);
    expect(screen.getByText("1 modules without questions")).toBeInTheDocument();
    // the picker stays: it belongs to the topic levels, which show their own "too few students" note
    expect(screen.getByLabelText("Module for the topic levels below")).toBeInTheDocument();
  });
});

describe("course content (Q1-17)", () => {
  it("shows the code as secondary text and levels as readable labels", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/kcs": [{ id: 1, module_id: 10, code: "k1", name: "Ohm", definition: "", difficulty: "basic", status: "active" }],
      "GET /courses/1/check-items": [], "GET /courses/1/misconceptions": [],
    }));
    renderApp("/courses/1/content");
    expect((await screen.findAllByText("Basic")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Active")).toBeInTheDocument();
    expect(screen.getByTitle("Module code")).toHaveTextContent("M1");
    expect(screen.getAllByText("Ohm's law").length).toBeGreaterThan(0);
  });
});

describe("materials (Q1-18)", () => {
  const file = { id: 1, module_id: null, filename: "syllabus.pdf", size_bytes: 20480, scan_status: "accepted", uploaded_at: "2026-11-01T00:00:00Z" };

  it("shows readable states, the index in plain words and a tooltip on the delete icon", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/materials": { index_version: 3, rebuild_job_id: null, materials: [file, { ...file, id: 2, filename: "b.pdf", scan_status: "indexed" }] },
    }));
    renderApp("/courses/1/materials");
    expect(await screen.findByText("Search index updated 3 times")).toBeInTheDocument();
    expect(screen.getAllByText("Accepted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Indexed").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Delete syllabus.pdf" })).toHaveAttribute("title", "Delete syllabus.pdf");
  });

  it("says when no index exists yet", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/materials": { index_version: 0, rebuild_job_id: null, materials: [] } }));
    renderApp("/courses/1/materials");
    expect(await screen.findByText("Search index not built yet")).toBeInTheDocument();
  });

  it("shows the server's refusal of a file at upload time", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/materials": { index_version: 1, rebuild_job_id: null, materials: [] },
      "POST /courses/1/materials": () => reply({ detail: "the privacy scan found student data: STUDENT_ID", code: "invalid" }, 422),
    }));
    renderApp("/courses/1/materials");
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText("File"), new File(["x"], "a.md", { type: "text/markdown" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/STUDENT_ID/);
  });
});

describe("AI assistant (Q1-19)", () => {
  it("gives request examples that fit any course", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/ai/drafts": [] }));
    renderApp("/courses/1/ai");
    expect(await screen.findByText(/For example: expand the material/)).not.toHaveTextContent(/patient/i);
  });
});

describe("members (Q1-20)", () => {
  const members = [
    { id: 1, role: "instructor", status: "active", account_id: 2, username: "ida", display_name: "Ida Instructor", email: "ida@example.test", created_at: "2026-09-01T00:00:00Z" },
    { id: 2, role: "student", status: "active", account_id: 5, username: "ana", display_name: "Ana Example", email: "ana@example.test", created_at: "2026-09-01T00:00:00Z" },
  ];
  const invite = { expires_at: null, uses: 2, max_uses: null, created_at: "2026-09-01T00:00:00Z", expired: false };

  it("has no Remove on the caller's own row, no infinity sign and says the code exists without claiming it was shown", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/members": members, "GET /courses/1/invite": invite }));
    renderApp("/courses/1/members");
    await screen.findByText("Ana Example");
    expect(screen.queryByRole("button", { name: "Remove Ida Instructor" })).toBeNull();
    expect(screen.getByRole("button", { name: "Remove Ana Example" })).toBeInTheDocument();
    expect(screen.queryByText(/∞/)).toBeNull();
    expect(screen.getByText(/Used 2 times, no limit/)).toHaveTextContent("No expiry");
    expect(screen.queryByText(/cannot be shown again/)).toBeNull();
    expect(screen.getByText(/only shown when it is created/)).toBeInTheDocument();
  });
});

describe("course settings (Q1-21)", () => {
  it("hints when the term is empty, has one Save per form and explains the connections", async () => {
    mockApi(instructorRoutes({
      "GET /courses": [{ ...COURSE, my_role: "instructor", term_label: "" }],
      "GET /courses/1/settings": { values: { visibility_mode: "A", local_only: false, routing_preference: "default", show_routing_progress: true }, version: 1 },
      "GET /courses/1/model-endpoints": [],
    }));
    renderApp("/courses/1/settings");
    expect(await screen.findByText(/Not set\. For example Fall 2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save course details" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Save settings" })).toBeInTheDocument();
    expect(screen.getByText(/The model on the course's own server/)).toBeInTheDocument();
    expect(screen.getByText(/Not used when Local only is on/)).toBeInTheDocument();
  });
});

describe("administration (Q1-22, Q1-23)", () => {
  const admin = { ...ME_INSTRUCTOR, system_role: "admin" as const };
  const settings = { version: 1, apply_state: "idle", values: {}, defaults: { local_llm_url: "http://real-host.internal:9000/v1", level_hysteresis: 0.05 } };

  it("uses a neutral placeholder for the local model URL and shows the deployment's value as text", async () => {
    mockApi({
      "GET /auth/me": admin, "GET /courses": [],
      "GET /admin/settings": settings, "GET /admin/statistics": { min_group: 5, courses: [], students_enrolled: 27, active_students_7d: null, questions_total: 0, questions_7d: 0 },
      "GET /admin/model-endpoints": [], "GET /admin/students": [], "GET /admin/staff": [],
    });
    renderApp("/admin");
    const field = await screen.findByLabelText("Local model URL");
    expect(field).toHaveAttribute("placeholder", "http://vllm.example:8000/v1");
    expect(field.getAttribute("placeholder")).not.toContain("real-host");
    expect(screen.getByText(/Default: http:\/\/real-host\.internal:9000\/v1/)).toBeInTheDocument();
    expect(screen.getByText(/A student changes level only after passing the limit/)).toBeInTheDocument();
    expect(screen.getByText("level_hysteresis")).toBeInTheDocument();
  });

  it("calls the system total enrolments and explains hidden cells", async () => {
    mockApi({
      "GET /auth/me": admin, "GET /courses": [],
      "GET /admin/settings": settings, "GET /admin/statistics": { min_group: 5, courses: [], students_enrolled: 27, active_students_7d: null, questions_total: 0, questions_7d: 0 },
      "GET /admin/model-endpoints": [], "GET /admin/students": [], "GET /admin/staff": [],
    });
    renderApp("/admin");
    expect(await screen.findByText("Enrolments (all courses)")).toBeInTheDocument();
    expect(screen.getByText(/Hidden: fewer than 5 students contributed/)).toBeInTheDocument();
  });
});

describe("login and password (Q1-09, Q1-12, Q1-24)", () => {
  it("shows the login error in French", async () => {
    mockApi({
      "GET /auth/me": reply({ detail: "no", code: "unauthenticated" }, 401),
      "POST /auth/login": () => reply({ detail: "invalid username or password", code: "unauthenticated" }, 401),
    });
    renderApp("/login", "fr");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/Nom d’utilisateur/), "x");
    await user.type(screen.getByLabelText(/^Mot de passe/), "y");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nom d’utilisateur ou mot de passe invalide.");
  });

  it("titles the login tab", async () => {
    mockApi({ "GET /auth/me": reply({ detail: "no", code: "unauthenticated" }, 401) });
    renderApp("/login");
    await screen.findByRole("heading", { level: 1 });
    expect(document.title).toBe("Log in · PACT");
  });

  it("calls the page Change your password with a way back, and Choose your password on the first login", async () => {
    mockApi({ "GET /auth/me": ME_STUDENT, "GET /courses": [] });
    const first = renderApp("/change-password");
    expect(await screen.findByRole("heading", { name: "Change your password" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cancel" })).toHaveAttribute("href", "/courses");
    first.unmount();

    mockApi({ "GET /auth/me": { ...ME_STUDENT, must_change_password: true }, "GET /courses": [] });
    renderApp("/change-password");
    expect(await screen.findByRole("heading", { name: "Choose your password" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Cancel" })).toBeNull();
  });
});

describe("Personalize (Q1-11)", () => {
  it("splits a text into sentences", () => {
    expect(sentences("One thing. Another thing! Last one? Yes.")).toEqual(["One thing.", "Another thing!", "Last one?", "Yes."]);
    expect(sentences("Use e.g. this.")).toEqual(["Use e.g. this."]);
  });

  it("shows the consent in short paragraphs and no empty step", async () => {
    mockApi(studentRoutes({
      "GET /courses/1/onboarding": { module_id: 10, consent_text: "First sentence. Second sentence.", consent_given: null,
        preference_questions: [], diagnostic: [] },
    }));
    renderApp("/courses/1/start");
    expect(await screen.findByText("First sentence.")).toBeInTheDocument();
    expect(screen.getByText("Second sentence.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/No questions are available/)).toBeNull());
    expect(screen.queryByRole("heading", { name: /diagnostic|check/i })).toBeNull();
  });
});

describe("sidebar course names (Q1-25)", () => {
  it("shows the full title on hover and sorts by course code", async () => {
    mockApi(instructorRoutes({
      "GET /courses": [
        { ...COURSE, id: 1, code: "MIT 6.002", title: "Circuits and Electronics", my_role: "instructor" },
        { ...COURSE, id: 2, code: "ECE 1000", title: "Fictional Circuits", my_role: "instructor" },
        { ...COURSE, id: 3, code: "MED 0000", title: "Medical Basics", my_role: "instructor" },
      ],
      "GET /courses/1/settings": { values: {}, version: 1 },
    }));
    renderApp("/courses/1/members");
    const select = await screen.findByRole("combobox", { name: "Courses" });
    expect(select).toHaveAttribute("title", "MIT 6.002 · Circuits and Electronics");
    const options = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["ECE 1000 · Fictional Circuits", "MED 0000 · Medical Basics", "MIT 6.002 · Circuits and Electronics"]);
  });
});
