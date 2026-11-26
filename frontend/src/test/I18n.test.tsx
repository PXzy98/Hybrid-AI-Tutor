import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { en } from "../i18n/en";
import { fr } from "../i18n/fr";
import { instructorRoutes, mockApi, reply, renderApp, studentRoutes } from "./helpers";

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

// an in-memory localStorage: the one jsdom gets from some Node versions has no methods
let store: Map<string, string>;
beforeEach(() => {
  store = new Map();
  vi.stubGlobal("localStorage", { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v) });
});
afterEach(() => vi.unstubAllGlobals());

describe("translation files", () => {
  it("translate every key, with the same placeholders, and nothing is left empty", () => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(en[key].trim(), key).not.toBe("");
      expect(fr[key].trim(), key).not.toBe("");
      expect(placeholders(fr[key]), key).toEqual(placeholders(en[key]));
    }
  });
});

describe("count messages", () => {
  it("use the singular for one in French and English", async () => {
    const { I18nProvider, useI18n } = await import("../i18n");
    const { render } = await import("@testing-library/react");
    const Probe = () => { const { t } = useI18n(); return <p>{t("survey.responsesN", { n: 1 })} / {t("survey.responsesN", { n: 2 })}</p>; };
    const { unmount } = render(<I18nProvider lang="fr"><Probe /></I18nProvider>);
    expect(screen.getByText("1 réponse / 2 réponses")).toBeInTheDocument();
    unmount();
    render(<I18nProvider lang="en"><Probe /></I18nProvider>);
    expect(screen.getByText("1 answer / 2 answers")).toBeInTheDocument();
  });
});

describe("language switch", () => {
  it("switches the login page to French, remembers the choice and sets the page language", async () => {
    mockApi({ "GET /auth/me": () => reply({ detail: "Not logged in", code: "forbidden" }, 401) });
    renderApp("/login");
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    await userEvent.setup().selectOptions(screen.getByLabelText("Language"), "fr");
    expect(screen.getByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    expect(store.get("tutor.lang")).toBe("fr");
    expect(document.documentElement.lang).toBe("fr");
  });

  it("shows the scan status of a material in French (V17 W6)", async () => {
    mockApi(instructorRoutes({
      "GET /courses/1/materials": { index_version: 1, rebuild_job_id: null, materials: [
        { id: 1, module_id: null, filename: "syllabus.md", size_bytes: 10, scan_status: "accepted", uploaded_at: "2026-11-01T00:00:00Z" }] },
    }));
    renderApp("/courses/1/materials", "fr");
    expect(await screen.findByText("syllabus.md")).toBeInTheDocument();
    expect(screen.getAllByText("Accepté").length).toBeGreaterThan(0);
    expect(screen.queryByText("Accepted")).toBeNull();
  });

  it("shows the student dashboard, the cloud notice and the English-only note in French", async () => {
    mockApi(studentRoutes());
    renderApp("/courses/1/chat", "fr");
    expect(await screen.findByRole("link", { name: "Ma progression" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quiz" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sondage de fin de session" })).toBeInTheDocument();
    expect(await screen.findByText(/peut être envoyée à un modèle infonuagique/)).toBeInTheDocument();
    expect(await screen.findByText(/Posez vos questions en anglais/)).toBeInTheDocument();
  });

  it("shows the instructor dashboard sections in French", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true } }));
    renderApp("/courses/1/overview", "fr");
    for (const name of ["Aperçu de la classe", "Étudiants", "Membres", "Fin de session / session suivante", "Quiz", "Sondage de fin de session"]) {
      expect(await screen.findByRole("link", { name })).toBeInTheDocument();
    }
  });
});
