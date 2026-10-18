import { request, type Schemas } from "./client";
import { askStream } from "./askStream";

export type Me = Schemas["Me"];
export type TopicInfo = Schemas["TopicInfo"];
export type AskBody = Schemas["AskBody"];
export type AskResponse = Schemas["AskResponse"];
export type RoutingOptions = Schemas["RoutingOptions"];
export type AdminConfig = Schemas["AdminConfig"];
export type RuntimeConfig = Schemas["RuntimeConfig"];
export type CheckItem = Schemas["CheckItemPublic"];
export type CheckResponse = Schemas["CheckResponse"];
export type OnboardingInfo = Schemas["OnboardingInfo"];
export type OnboardingBody = Schemas["OnboardingBody"];
export type OnboardingResult = Schemas["OnboardingResult"];
export type Profile = Schemas["Profile"];
export type Preferences = Schemas["Preferences"];
export type FeedbackAction = Schemas["FeedbackBody"]["action"];

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
};

export const admin = {
  config: () => request<AdminConfig>("GET", `${V1}/admin/config`),
  saveConfig: (values: RuntimeConfig) => request<AdminConfig>("PUT", `${V1}/admin/config`, values),
};
