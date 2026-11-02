import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Layout from "../components/Layout";
import { I18nProvider, type Lang } from "../i18n";
import { en } from "../i18n/en";
import { fr } from "../i18n/fr";
import Admin from "../pages/Admin";
import Chat from "../pages/Chat";
import Login from "../pages/Login";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
const ME = { id: 1, username: "s.one", display_name: "S One", role: "student", must_change_password: false };

function mount(element: JSX.Element, lang?: Lang, path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><I18nProvider lang={lang}>{element}</I18nProvider></MemoryRouter>
    </QueryClientProvider>,
  );
}

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
  it("switches the interface to French, remembers the choice and sets the page language", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Not logged in" }, 401)));
    mount(<Login />, undefined, "/login");
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    await userEvent.setup().selectOptions(screen.getByLabelText("Language"), "fr");
    expect(screen.getByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nom d’utilisateur")).toBeInTheDocument();
    expect(store.get("tutor.lang")).toBe("fr");
    expect(document.documentElement.lang).toBe("fr");
  });

  it("starts in the saved language", async () => {
    store.set("tutor.lang", "fr");
    mount(<Layout me={ME as never}><p>page</p></Layout>);
    expect(screen.getByRole("link", { name: "Ce que je sais" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("ce ne sont pas des conseils médicaux");
  });
});

describe("pages in both languages", () => {
  function stubChat() {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("routing/options")) return json({ show_progress: true, default_method: "lr", methods: [{ id: "lr", label: "LR" }] });
      if (url.endsWith("/topics")) return json([{ id: "high_blood_pressure", name: "High Blood Pressure" }]);
      if (url.endsWith("learner/me")) return json({ personalized: false });
      throw new Error(`Unexpected URL ${url}`);
    }));
  }

  it("French chat asks for questions in English, because the privacy filter only knows English", async () => {
    stubChat();
    mount(<Chat />, "fr");
    expect(await screen.findByRole("button", { name: "Envoyer" })).toBeInTheDocument();
    expect(screen.getByText(/Posez vos questions en anglais/)).toBeInTheDocument();
    expect(await screen.findByText(/pas encore adaptées/)).toBeInTheDocument();
  });

  it("English chat has no such note", async () => {
    stubChat();
    mount(<Chat />, "en");
    expect(await screen.findByRole("button", { name: "Send" })).toBeInTheDocument();
    expect(screen.queryByText(/privacy filter only recognizes English/)).not.toBeInTheDocument();
  });

  it("instructor dashboard tabs and student list in French", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([{ id: 7, username: "s.one", display_name: "S One", active: true,
      must_change_password: false, created_at: "2026-10-12T10:00:00Z", last_login_at: null }])));
    mount(<Admin />, "fr", "/students");
    expect(screen.getByRole("heading", { name: "Tableau de bord de l’enseignant" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Résumé de la classe" })).toBeInTheDocument();
    expect(await screen.findByText("Étudiants (1)")).toBeInTheDocument();
    expect(screen.getByText("jamais")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réinitialiser le mot de passe" })).toBeInTheDocument();
  });
});
