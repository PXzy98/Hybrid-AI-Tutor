import { act, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTheme } from "../components/theme";
import { mockApi, renderApp, studentRoutes } from "./helpers";

// an in-memory localStorage: the one jsdom gets from some Node versions has no methods
const store = new Map<string, string>();
beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v),
    removeItem: (k: string) => store.delete(k) });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
});

/** A window whose width can be changed: matchMedia answers min-width queries and tells its listeners. */
function stubWidth(initial: number) {
  let width = initial;
  const queries: { query: string; listeners: Set<() => void> }[] = [];
  const matches = (query: string) => {
    const min = /min-width:\s*([\d.]+)rem/.exec(query);
    return min ? width >= Number(min[1]) * 16 : false;
  };
  vi.stubGlobal("matchMedia", (query: string) => {
    const entry = { query, listeners: new Set<() => void>() };
    queries.push(entry);
    return {
      get matches() { return matches(query); },
      addEventListener: (_: string, listener: () => void) => entry.listeners.add(listener),
      removeEventListener: (_: string, listener: () => void) => entry.listeners.delete(listener),
    };
  });
  return (next: number) => {
    width = next;
    act(() => queries.forEach((q) => q.listeners.forEach((listener) => listener())));
  };
}

describe("theme", () => {
  it("is one choice for every menu that shows it", () => {
    // the desktop sidebar stays mounted next to the mobile sheet: both account menus use the hook
    const desktop = renderHook(() => useTheme());
    const mobile = renderHook(() => useTheme());
    act(() => mobile.result.current[1]("dark"));
    expect(desktop.result.current[0]).toBe("dark");
    expect(document.documentElement).toHaveClass("dark");
    act(() => desktop.result.current[1]("light"));  // a choice in the other menu still applies
    expect(mobile.result.current[0]).toBe("light");
    expect(document.documentElement).not.toHaveClass("dark");
    expect(store.get("tutor.theme")).toBe("light");
  });
});

describe("sidebar sheet", () => {
  it("closes when the window grows to the desktop layout", async () => {
    const resize = stubWidth(500);
    mockApi(studentRoutes());
    renderApp("/courses/1/chat");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Show the sidebar" }));
    expect(await screen.findByRole("dialog", { name: "Courses, modules and conversations" })).toBeInTheDocument();
    resize(1200);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
