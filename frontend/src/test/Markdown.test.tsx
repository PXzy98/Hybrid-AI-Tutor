import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import Markdown from "../components/Markdown";

it("renders bold text, lists and tables instead of showing the markup", () => {
  render(<Markdown>{"This is **important**.\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |"}</Markdown>);
  expect(screen.getByText("important").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(screen.getByRole("table")).toBeInTheDocument();
  expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
});

it("renders math and does not render raw HTML", () => {
  const { container } = render(<Markdown>{"Energy $E = mc^2$ <script>alert(1)</script>"}</Markdown>);
  expect(container.querySelector(".katex")).not.toBeNull();
  expect(container.querySelector("script")).toBeNull();
});
