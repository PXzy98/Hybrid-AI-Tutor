import { lazy, Suspense } from "react";

// react-markdown, remark, rehype and KaTeX (with its CSS) load as their own chunk.
const Markdown = lazy(() => import("./Markdown"));

/** Markdown that loads on first use; until then the text shows as it is, so an answer never waits for the renderer. */
export default function LazyMarkdown({ children }: { children: string }) {
  return (
    <Suspense fallback={<div className="markdown whitespace-pre-wrap">{children}</div>}>
      <Markdown>{children}</Markdown>
    </Suspense>
  );
}
