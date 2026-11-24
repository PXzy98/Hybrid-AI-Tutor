import { act, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useScrollMemory } from "../components/shell/useScrollMemory";

let navigate: ReturnType<typeof useNavigate>;

/** The shell's scrolling element in small: jsdom does no layout, so scrollTop is a plain stored number. */
function Shell() {
  const ref = useRef<HTMLElement>(null);
  useScrollMemory(ref);
  navigate = useNavigate();
  return (
    <main ref={ref} data-testid="main">
      <Routes>
        <Route path="*" element={<p>page</p>} />
      </Routes>
    </main>
  );
}

function setup(path = "/courses/1/quizzes") {
  render(<MemoryRouter initialEntries={[path]}><Shell /></MemoryRouter>);
  const main = screen.getByTestId("main");
  let top = 0;
  Object.defineProperty(main, "scrollTop", { configurable: true, get: () => top, set: (v: number) => { top = v; } });
  const scrollTo = (v: number) => {
    top = v;
    fireEvent.scroll(main);
  };
  const go = (to: string | number) => act(() => { void (typeof to === "number" ? navigate(to) : navigate(to)); });
  return { top: () => top, scrollTo, go };
}

describe("scroll position of the shell (V24)", () => {
  it("starts a new page at the top", () => {
    const s = setup();
    s.scrollTo(900);  // the end of a finished quiz
    s.go("/courses/1/progress");
    expect(s.top()).toBe(0);
  });

  it("returns to where a page was left on back and forward", () => {
    const s = setup();
    s.scrollTo(900);
    s.go("/courses/1/progress");
    s.scrollTo(250);
    s.go(-1);
    expect(s.top()).toBe(900);
    s.go(1);
    expect(s.top()).toBe(250);
  });

  it("keeps the position when only the query string changes or the link goes to an anchor", () => {
    const s = setup("/courses/1/students");
    s.scrollTo(400);
    s.go("/courses/1/students?filter=weak");
    expect(s.top()).toBe(400);
    s.go("/courses/1/settings#next-term");
    expect(s.top()).toBe(400);  // the page scrolls to its own anchor
  });
});
