import "katex/dist/katex.min.css";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

// An image would make the browser request its address by itself, outside the cloud gate, and tell that host the
// student's IP address; so only the alt text is shown. Links open in a new tab without the opener or a referrer.
const components: Components = {
  img: ({ alt }) => (alt ? <span>{alt}</span> : null),
  a: ({ node: _node, href, children, ...rest }) => {
    const external = !!href && /^https?:\/\//i.test(href);
    return (
      <a {...rest} href={href} rel="noopener noreferrer nofollow" {...(external ? { target: "_blank" } : {})}>
        {children}
      </a>
    );
  },
};

// Models often write LaTeX as \( ... \) and \[ ... \]; Markdown reads "\(" as an escaped "(" and the formula is shown
// as raw text ("(V_{th})"). These delimiters become $ ... $ and $$ ... $$, outside code (V17 W20).
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/;

function mathDelimiters(text: string): string {
  return text
    .split(CODE)
    .map((part, i) => (i % 2 === 1 ? part : part
      .replace(/\\\[([\s\S]+?)\\\]/g, (_m, body: string) => `\n$$\n${body.trim()}\n$$\n`)
      .replace(/\\\(([\s\S]+?)\\\)/g, (_m, body: string) => `$${body.trim()}$`)))
    .join("");
}

/** Renders a tutor answer as Markdown (GitHub flavour, KaTeX math), styled by `.markdown` in index.css. Raw HTML in
 *  the text is not rendered; images are shown as their alt text. */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {mathDelimiters(children)}
      </ReactMarkdown>
    </div>
  );
}
