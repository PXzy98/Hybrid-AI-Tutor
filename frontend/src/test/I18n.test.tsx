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

  it("shows the student dashboard, the cloud notice and the English-only note in French", async () => {
    mockApi(studentRoutes());
    renderApp("/courses/1/chat", "fr");
    expect(await screen.findByRole("tab", { name: "Ma progression" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Quiz" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Sondage de fin de session" })).toBeInTheDocument();
    expect(screen.getByText(/peut être envoyée à un modèle infonuagique/)).toBeInTheDocument();
    expect(screen.getByText(/Posez vos questions en anglais/)).toBeInTheDocument();
  });

  it("shows the instructor dashboard tabs in French", async () => {
    mockApi(instructorRoutes({ "GET /courses/1/class-summary": { topic: "t", min_group: 5, suppressed: true } }));
    renderApp("/courses/1/overview", "fr");
    for (const name of ["Aperçu de la classe", "Étudiants", "Membres", "Fin de session", "Quiz", "Sondage de fin de session"]) {
      expect(await screen.findByRole("tab", { name })).toBeInTheDocument();
    }
  });
});
