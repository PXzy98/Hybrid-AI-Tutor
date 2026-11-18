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

it("never renders an image, only its alt text", () => {
  const { container } = render(
    <Markdown>{"See ![a lung](https://tracker.example/p.png) and ![][ref]\n\n[ref]: https://tracker.example/q.png"}</Markdown>,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText("a lung")).toBeInTheDocument();
});

it("gives external links a safe rel and opens them in a new tab", () => {
  render(<Markdown>{"[site](https://example.org/x) and [here](#part) and [bad](javascript:alert(1))"}</Markdown>);
  const site = screen.getByRole("link", { name: "site" });
  expect(site).toHaveAttribute("rel", "noopener noreferrer nofollow");
  expect(site).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: "here" })).not.toHaveAttribute("target");
  expect(screen.queryByRole("link", { name: "bad" })?.getAttribute("href") ?? "").not.toMatch(/^javascript:/i);
});
