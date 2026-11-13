import { askStream } from "./askStream";
import { download, request, resetCsrf, type Schemas, upload } from "./client";

export type Me = Schemas["MeOut"];
export type Course = Schemas["CourseOut"];
export type Module = Schemas["ModuleOut"];
export type Kc = Schemas["KcOut"];
export type CheckItemFull = Schemas["ItemOut"];
export type Member = Schemas["MemberOut"];
export type ImportReport = Schemas["ImportReportOut"];
export type Invite = Schemas["InviteOut"];
export type CourseSettings = Schemas["CourseSettingsOut"];
export type CourseValues = Schemas["CourseValues"];
export type AskBody = Schemas["AskIn"];
export type AskResponse = Schemas["AskOut"];
export type Conversation = Schemas["ConversationOut"];
export type ConversationDetail = Schemas["ConversationDetailOut"];
export type CheckItem = Schemas["CheckItemPublic"];
export type CheckResponse = Schemas["CheckResponse"];
export type Onboarding = Schemas["OnboardingOut"];
export type OnboardingBody = Schemas["OnboardingIn"];
export type OnboardingResult = Schemas["OnboardingResult"];
export type CourseProfile = Schemas["CourseProfileOut"];
export type Visibility = Schemas["VisibilityOut"];
export type VisibilityAction = Schemas["VisibilityIn"]["action"];
export type ClassSummary = Schemas["ClassSummary"];
export type StudentOverview = Schemas["InstructorProfileView"];
export type Plan = Schemas["PlanOut"];
export type PlanBody = Schemas["PlanIn"];
export type EndTermResult = Schemas["EndTermOut"];
export type Quiz = Schemas["QuizOut"];
export type StudentQuiz = Schemas["StudentQuizOut"];
export type QuizQuestion = Schemas["QuizQuestion"];
export type QuizResults = Schemas["QuizResults"];
export type OwnAttempt = Schemas["OwnAttempt"];
export type QuizBody = Schemas["QuizIn"];
export type QuizPatch = Schemas["QuizPatch"];
export type DraftBody = Schemas["DraftIn"];
export type Job = Schemas["JobOut"];
export type Survey = Schemas["SurveyOut"];
export type SurveyAnswers = Schemas["SurveyAnswers"];
export type Materials = Schemas["MaterialsOut"];
export type Material = Schemas["MaterialOut"];
export type AiDraft = Schemas["AiDraftOut"];
export type AiDraftAccept = Schemas["AiDraftAcceptOut"];
export type AiDraftSummary = Schemas["AiDraftSummary"];
export type AiDraftKind = Schemas["AiDraftIn"]["kind"];
export type AiDraftStatus = Schemas["AiDraftSummary"]["status"];
export type Insights = Schemas["InsightsOut"];
export type Evaluation = Schemas["EvaluationOut"];
export type EvaluationSummary = Schemas["EvaluationSummary"];
export type EvaluationQuestion = Schemas["QuestionIn"];
export type Difficulty = Schemas["KcOut"]["difficulty"];

const c = (id: number) => `/courses/${id}`;
const body = <T>(value: T) => value;

export const api = {
  // account
  csrf: () => request<Schemas["CsrfOut"]>("GET", "/auth/csrf"),
  login: (username: string, password: string) => request<Me>("POST", "/auth/login", { username, password }),
  logout: async () => {
    await request<void>("POST", "/auth/logout");
    resetCsrf();
  },
  me: () => request<Me>("GET", "/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<Me>("POST", "/auth/change-password", { current_password, new_password }),
  join: (input: Schemas["JoinIn"]) => request<Schemas["JoinOut"]>("POST", "/auth/join", input),

  // courses and content
  courseTypes: () => request<string[]>("GET", "/course-types"),
  courses: () => request<Course[]>("GET", "/courses"),
  createCourse: (input: Schemas["CourseIn"]) => request<Course>("POST", "/courses", input),
  course: (id: number) => request<Course>("GET", c(id)),
  updateCourse: (id: number, changes: Schemas["CoursePatch"]) => request<Course>("PATCH", c(id), changes),
  modules: (id: number) => request<Module[]>("GET", `${c(id)}/modules`),
  createModule: (id: number, input: Schemas["ModuleIn"]) => request<Module>("POST", `${c(id)}/modules`, input),
  updateModule: (id: number, moduleId: number, changes: Schemas["ModulePatch"]) =>
    request<Module>("PATCH", `${c(id)}/modules/${moduleId}`, changes),
  deleteModule: (id: number, moduleId: number) => request<void>("DELETE", `${c(id)}/modules/${moduleId}`),
  reorderModules: (id: number, ids: number[]) => request<Module[]>("POST", `${c(id)}/modules/reorder`, body({ module_ids: ids })),
  kcs: (id: number) => request<Kc[]>("GET", `${c(id)}/kcs`),
  createKc: (id: number, input: Schemas["KcIn"]) => request<Kc>("POST", `${c(id)}/kcs`, input),
  updateKc: (id: number, kcId: number, changes: Schemas["KcPatch"]) => request<Kc>("PATCH", `${c(id)}/kcs/${kcId}`, changes),
  checkItems: (id: number) => request<CheckItemFull[]>("GET", `${c(id)}/check-items`),
  createCheckItem: (id: number, input: Schemas["ItemIn"]) => request<CheckItemFull>("POST", `${c(id)}/check-items`, input),
  updateCheckItem: (id: number, itemId: number, changes: Schemas["ItemPatch"]) =>
    request<CheckItemFull>("PATCH", `${c(id)}/check-items/${itemId}`, changes),

  // members, invitation, settings, end of term
  members: (id: number) => request<Member[]>("GET", `${c(id)}/members`),
  importMembers: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<ImportReport>(`${c(id)}/members/import`, form);
  },
  addInstructor: (id: number, email: string) => request<Member>("POST", `${c(id)}/members/instructors`, { email }),
  removeMember: (id: number, memberId: number) => request<void>("DELETE", `${c(id)}/members/${memberId}`),
  resetMemberPassword: (id: number, memberId: number) =>
    request<Schemas["TemporaryPasswordOut"]>("POST", `${c(id)}/members/${memberId}/reset-password`),
  invite: (id: number) => request<Invite | null>("GET", `${c(id)}/invite`),
  rotateInvite: (id: number) => request<Schemas["NewInviteOut"]>("POST", `${c(id)}/invite/rotate`),
  courseSettings: (id: number) => request<CourseSettings>("GET", `${c(id)}/settings`),
  saveCourseSettings: (id: number, values: CourseValues, version: number) =>
    request<CourseSettings>("PUT", `${c(id)}/settings`, { values, version }),
  endTerm: (id: number) => request<EndTermResult>("POST", `${c(id)}/end-term`, { confirm: true }),
  downloadExport: (id: number, exportId: string) => download(`${c(id)}/exports/${encodeURIComponent(exportId)}`),

  // student learning
  askStream,
  check: (id: number, item_id: string, choice: string) =>
    request<CheckResponse>("POST", `${c(id)}/check`, { item_id, choice }),
  conversations: (id: number) => request<Conversation[]>("GET", `${c(id)}/conversations`),
  conversation: (id: number, conversationId: string) =>
    request<ConversationDetail>("GET", `${c(id)}/conversations/${encodeURIComponent(conversationId)}`),
  onboarding: (id: number, moduleId: number) => request<Onboarding>("GET", `${c(id)}/onboarding?module_id=${moduleId}`),
  submitOnboarding: (id: number, input: OnboardingBody) => request<OnboardingResult>("POST", `${c(id)}/onboarding`, input),
  profile: (id: number) => request<CourseProfile>("GET", `${c(id)}/me/profile`),
  setVisibility: (id: number, action: VisibilityAction) => request<Visibility>("POST", `${c(id)}/me/visibility`, { action }),

  // instructor views of learners
  classSummary: (id: number, moduleId: number) =>
    request<ClassSummary>("GET", `${c(id)}/class-summary?module_id=${moduleId}`),
  studentOverview: (id: number, studentId: string) =>
    request<StudentOverview>("GET", `${c(id)}/students/${encodeURIComponent(studentId)}/overview`),
  studentPlan: (id: number, studentId: string) => request<Plan>("GET", `${c(id)}/students/${encodeURIComponent(studentId)}/plan`),
  savePlan: (id: number, studentId: string, plan: PlanBody) =>
    request<Plan>("PUT", `${c(id)}/students/${encodeURIComponent(studentId)}/plan`, plan),

  // materials
  materials: (id: number) => request<Materials>("GET", `${c(id)}/materials`),
  uploadMaterial: (id: number, file: File, moduleId: number | null) => {
    const form = new FormData();
    form.append("file", file);
    if (moduleId !== null) form.append("module_id", String(moduleId));
    return upload<Schemas["UploadOut"]>(`${c(id)}/materials`, form);
  },
  deleteMaterial: (id: number, materialId: number) => request<void>("DELETE", `${c(id)}/materials/${materialId}`),
  deleteLearningData: (id: number) => request<void>("DELETE", `${c(id)}/me/learning-data`),

  // quizzes
  quizzes: (id: number) => request<Quiz[]>("GET", `${c(id)}/quizzes`),
  studentQuizzes: (id: number) => request<StudentQuiz[]>("GET", `${c(id)}/quizzes`),
  createQuiz: (id: number, input: QuizBody) => request<Quiz>("POST", `${c(id)}/quizzes`, input),
  updateQuiz: (id: number, quizId: number, changes: QuizPatch) => request<Quiz>("PATCH", `${c(id)}/quizzes/${quizId}`, changes),
  deleteQuiz: (id: number, quizId: number) => request<void>("DELETE", `${c(id)}/quizzes/${quizId}`),
  draftQuiz: (id: number, quizId: number, input: DraftBody) =>
    request<Schemas["DraftOut"]>("POST", `${c(id)}/quizzes/${quizId}/drafts`, input),
  job: (id: number, jobId: number) => request<Job>("GET", `${c(id)}/jobs/${jobId}`),
  attemptQuiz: (id: number, quizId: number, answers: number[]) =>
    request<OwnAttempt>("POST", `${c(id)}/quizzes/${quizId}/attempt`, { answers }),
  quizResults: (id: number, quizId: number) => request<QuizResults>("GET", `${c(id)}/quizzes/${quizId}/results`),

  // end-of-term survey
  survey: (id: number) => request<Survey>("GET", `${c(id)}/survey`),
  setSurveyWindow: (id: number, opens_at: string, closes_at: string) =>
    request<Survey>("PUT", `${c(id)}/survey`, { opens_at, closes_at }),
  answerSurvey: (id: number, answers: SurveyAnswers) => request<Survey>("POST", `${c(id)}/survey/responses`, answers),

  // instructor AI (tiers 1 to 4) and class insights
  aiDrafts: (id: number, status?: AiDraftStatus) =>
    request<AiDraftSummary[]>("GET", `${c(id)}/ai/drafts${status ? `?status=${status}` : ""}`),
  aiDraft: (id: number, draftId: number) => request<AiDraft>("GET", `${c(id)}/ai/drafts/${draftId}`),
  createAiDraft: (id: number, input: Schemas["AiDraftIn"]) => request<AiDraft>("POST", `${c(id)}/ai/drafts`, input),
  updateAiDraft: (id: number, draftId: number, content: Record<string, unknown>) =>
    request<AiDraft>("PATCH", `${c(id)}/ai/drafts/${draftId}`, { content }),
  acceptAiDraft: (id: number, draftId: number, moduleId: number | null) =>
    request<Schemas["AiDraftAcceptOut"]>("POST", `${c(id)}/ai/drafts/${draftId}/accept`, moduleId === null ? {} : { module_id: moduleId }),
  discardAiDraft: (id: number, draftId: number) => request<void>("DELETE", `${c(id)}/ai/drafts/${draftId}`),
  insights: (id: number) => request<Insights>("GET", `${c(id)}/insights`),
  evaluations: (id: number) => request<EvaluationSummary[]>("GET", `${c(id)}/ai/evaluations`),
  evaluation: (id: number, evalId: number) => request<Evaluation>("GET", `${c(id)}/ai/evaluations/${evalId}`),
  createEvaluation: (id: number, input: Schemas["EvaluationIn"]) => request<Evaluation>("POST", `${c(id)}/ai/evaluations`, input),
  setEvaluationQuestions: (id: number, evalId: number, questions: EvaluationQuestion[]) =>
    request<Evaluation>("PUT", `${c(id)}/ai/evaluations/${evalId}/questions`, { questions }),
  runEvaluation: (id: number, evalId: number, confirm_cloud: boolean) =>
    request<Evaluation>("POST", `${c(id)}/ai/evaluations/${evalId}/run`, { confirm_cloud }),
  spotCheck: (id: number, evalId: number, questionId: number, agrees_with_judge: boolean) =>
    request<Evaluation>("PATCH", `${c(id)}/ai/evaluations/${evalId}/results/${questionId}`, { agrees_with_judge }),
};
