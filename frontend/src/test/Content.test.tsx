import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { admin, type ContentStatus } from "../api/endpoints";
import ContentPage from "../pages/admin/Content";

function data(): ContentStatus {
  return { serve_unreviewed: false, topics: [{ topic: "asthma", name: "Asthma", kcs: 3, items: 4,
    items_reviewed: 0, misconceptions: 2, misconceptions_reviewed: 0, materials: [], rag_materials: [
      { name: "asthma.txt", origin: "builtin", source: "https://medlineplus.gov/asthma.html",
        indexed: true, passage_count: 11, message: null },
    ] }] };
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ContentPage /></QueryClientProvider>);
}
afterEach(() => vi.restoreAllMocks());

it("shows built-in searchable source material even with no uploads", async () => {
  vi.spyOn(admin, "content").mockResolvedValue(data());
  mount();
  expect(await screen.findByText("asthma.txt")).toBeInTheDocument();
  expect(screen.getByText("Searchable · 11 passages")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute("href", "https://medlineplus.gov/asthma.html");
  expect(screen.getByText("No uploads yet.")).toBeInTheDocument();
});

it("refreshes upload inventory after successful indexing", async () => {
  const value = data();
  vi.spyOn(admin, "content").mockImplementation(async () => structuredClone(value));
  const upload = vi.spyOn(admin, "uploadMaterial").mockImplementation(async () => {
    value.topics[0].rag_materials!.push({ name: "lecture.txt", origin: "uploaded", source: "course/asthma/lecture.txt",
      indexed: true, passage_count: 1, message: null });
    return { file: { name: "lecture.txt", size_bytes: 10, uploaded_at: "2026-10-18T00:00:00Z" }, ingested: true };
  });
  mount();
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText("Course material file"), new File(["Course text"], "lecture.txt", { type: "text/plain" }));
  await user.click(screen.getByRole("button", { name: /^Upload$/ }));
  expect(await screen.findByText("Uploaded and searchable.")).toBeInTheDocument();
  expect(await screen.findByText("lecture.txt")).toBeInTheDocument();
  expect(upload).toHaveBeenCalledWith("asthma", expect.any(File), false);
});

it("shows a saved-but-unindexed parse error instead of claiming success", async () => {
  vi.spyOn(admin, "content").mockResolvedValue(data());
  vi.spyOn(admin, "uploadMaterial").mockResolvedValue({
    file: { name: "scan.pdf", size_bytes: 100, uploaded_at: "2026-10-18T00:00:00Z" }, ingested: false,
    ingest_error: "Scanned PDFs require OCR before uploading.",
  });
  mount();
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText("Course material file"), new File(["scan"], "scan.pdf", { type: "application/pdf" }));
  await user.click(screen.getByRole("button", { name: /^Upload$/ }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("File saved, but not searchable."));
  expect(screen.getByRole("status")).toHaveTextContent("OCR");
});
