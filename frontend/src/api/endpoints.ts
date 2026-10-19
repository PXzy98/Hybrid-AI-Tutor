import { request, type Schemas, upload } from "./client";
import { askStream } from "./askStream";

export type Me = Schemas["Me"];
export type TopicInfo = Schemas["TopicInfo"];
export type AskBody = Schemas["AskBody"];
export type AskResponse = Schemas["AskResponse"];
export type RoutingOptions = Schemas["RoutingOptions"];
export type CheckItem = Schemas["CheckItemPublic"];
export type CheckResponse = Schemas["CheckResponse"];
export type OnboardingInfo = Schemas["OnboardingInfo"];
export type OnboardingBody = Schemas["OnboardingBody"];
export type OnboardingResult = Schemas["OnboardingResult"];
export type Profile = Schemas["Profile"];
export type Preferences = Schemas["Preferences"];
export type FeedbackAction = Schemas["FeedbackBody"]["action"];

export type SurveySubmission = Schemas["SurveySubmission"];
export type SurveyTopicSummary = Schemas["SurveyTopicSummary"];
export type SurveySummary = Schemas["SurveySummary"];

export type StudentAccount = Schemas["StudentAccountOut"];
export type CreatedStudent = Schemas["CreatedStudent"];
export type TemporaryPassword = Schemas["TemporaryPassword"];
export type AdminConfig = Schemas["AdminConfig"];
export type RuntimeConfig = Schemas["RuntimeConfig"];
export type ClassSummary = Schemas["ClassSummary"];
export type LogPage = Schemas["LogPage"];
export type ContentStatus = Schemas["ContentStatus"];
export type UploadResult = Schemas["UploadResult"];

const V1 = "/api/v1";

export const api = {
  login: (username: string, password: string) =>
    request<Me>("POST", `${V1}/auth/login`, { username, password }),
  logout: () => request<void>("POST", `${V1}/auth/logout`),
  me: () => request<Me>("GET", `${V1}/auth/me`),
  changePassword: (current_password: string, new_password: string) =>
    request<Me>("POST", `${V1}/auth/change-password`, { current_password, new_password }),

  topics: () => request<TopicInfo[]>("GET", `${V1}/topics`),
  ask: (body: AskBody) => request<AskResponse>("POST", `${V1}/ask`, body),
  askStream,
  routingOptions: () => request<RoutingOptions>("GET", `${V1}/routing/options`),
  check: (item_id: string, choice: string, session_id = "") =>
    request<CheckResponse>("POST", `${V1}/check`, { item_id, choice, session_id }),

  onboardingInfo: (topic: string) =>
    request<OnboardingInfo>("GET", `${V1}/onboarding?topic=${encodeURIComponent(topic)}`),
  submitOnboarding: (body: OnboardingBody) => request<OnboardingResult>("POST", `${V1}/onboarding`, body),

  profile: () => request<Profile>("GET", `${V1}/learner/me`),
  resetProfile: () => request<void>("DELETE", `${V1}/learner/me`),
  feedback: (action: FeedbackAction) => request<Preferences>("POST", `${V1}/learner/me/preferences`, { action }),
  submitSurvey: (body: SurveySubmission) => request<{ saved: boolean }>("POST", `${V1}/survey`, body),
};

const ADMIN = `${V1}/admin`;
const q = encodeURIComponent;

/** Instructor dashboard (design §8.3): account data and aggregates only. */
export const admin = {
  students: () => request<StudentAccount[]>("GET", `${ADMIN}/students`),
  createStudent: (username: string, display_name: string) =>
    request<CreatedStudent>("POST", `${ADMIN}/students`, { username, display_name }),
  updateStudent: (id: number, changes: { display_name?: string; active?: boolean }) =>
    request<StudentAccount>("PATCH", `${ADMIN}/students/${id}`, changes),
  resetPassword: (id: number) => request<TemporaryPassword>("POST", `${ADMIN}/students/${id}/reset-password`),
  deleteStudent: (id: number) => request<void>("DELETE", `${ADMIN}/students/${id}`),

  config: () => request<AdminConfig>("GET", `${ADMIN}/config`),
  saveConfig: (values: RuntimeConfig) => request<AdminConfig>("PUT", `${ADMIN}/config`, values),
  classSummary: (topic: string) => request<ClassSummary>("GET", `${ADMIN}/class-summary?topic=${q(topic)}`),
  logs: (page: number, pageSize = 20) =>
    request<LogPage>("GET", `${ADMIN}/logs?page=${page}&page_size=${pageSize}`),
  content: () => request<ContentStatus>("GET", `${ADMIN}/content`),
  surveySummary: () => request<SurveySummary>("GET", `${ADMIN}/survey-summary`),
  uploadMaterial: (topic: string, file: File, replace: boolean) => {
    const form = new FormData();
    form.append("file", file);
    return upload<UploadResult>(`${ADMIN}/topics/${q(topic)}/materials?replace=${replace}`, form);
  },
};
