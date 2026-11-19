import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import { formatDate, formatDateTime, formatDay } from "../lib/format";
import Composer from "../pages/student/chat/Composer";

function setup() {
  const onSubmit = vi.fn();
  render(
    <I18nProvider lang="en">
      <Composer value="hello" onChange={() => undefined} onSubmit={onSubmit} onStop={() => undefined}
                pending={false} scopeLabel="All" localOnly />
    </I18nProvider>,
  );
  return { box: screen.getByRole("textbox"), onSubmit };
}

describe("composer Enter", () => {
  it("sends on a plain Enter", () => {
    const { box, onSubmit } = setup();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not send on Shift+Enter", () => {
    const { box, onSubmit } = setup();
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not send while an IME composes (isComposing, or keyCode 229 as Safari reports it)", () => {
    const { box, onSubmit } = setup();
    fireEvent.keyDown(box, { key: "Enter", isComposing: true });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229 });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("date formatting", () => {
  const when = "2026-03-05T15:04:00Z";

  it("follows the interface language", () => {
    expect(formatDate(when, "en")).toBe(new Date(when).toLocaleDateString("en-CA"));
    expect(formatDate(when, "fr")).toBe(new Date(when).toLocaleDateString("fr-CA"));
    expect(formatDateTime(when, "en")).toBe(new Date(when).toLocaleString("en-CA"));
    expect(formatDateTime(when, "fr")).toBe(new Date(when).toLocaleString("fr-CA"));
  });

  it("shows a date-only day as that day in every time zone", () => {
    // a weekly bucket starts on Monday 2026-11-16; west of UTC, local formatting would show Sunday the 15th
    expect(formatDay("2026-11-16", "en")).toBe("2026-11-16");
    expect(formatDay("2026-11-16", "fr")).toBe(new Date(Date.UTC(2026, 10, 16)).toLocaleDateString("fr-CA", { timeZone: "UTC" }));
  });

  it("writes the time of day differently in the two languages", () => {
    // en-CA uses "p.m." and fr-CA a 24-hour clock with "h"
    expect(formatDateTime("2026-03-05T20:04:00Z", "en")).not.toBe(formatDateTime("2026-03-05T20:04:00Z", "fr"));
  });
});
