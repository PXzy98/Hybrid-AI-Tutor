// WCAG 2.1 contrast of the theme tokens in src/index.css, light and dark.
// oklch -> OKLab -> linear sRGB -> relative luminance -> ratio. Exits 1 when a text pair is under 4.5:1 or a
// boundary pair (focus ring, control border) under 3:1. Run with `npm run check:contrast`.
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");

function tokens(selector) {
  const block = css.match(new RegExp(`(^|\\n)${selector.replace(".", "\\.")} \\{([^}]*)\\}`))[2];
  const out = {};
  for (const [, name, l, c, h] of block.matchAll(/--([\w-]+):\s*oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)/g)) {
    out[name] = [Number(l), Number(c), Number(h)];
  }
  return out;
}

function luminance([l, c, h]) {
  const a = c * Math.cos((h * Math.PI) / 180);
  const b = c * Math.sin((h * Math.PI) / 180);
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const clip = (v) => Math.min(1, Math.max(0, v));
  const r = clip(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_);
  const g = clip(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_);
  const bl = clip(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_);
  return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
}

const ratio = (x, y) => {
  const [hi, lo] = [luminance(x), luminance(y)].sort((p, q) => q - p);
  return (hi + 0.05) / (lo + 0.05);
};

// [foreground, background, minimum]
const PAIRS = [
  ...["background", "sidebar", "card", "accent", "muted"].map((bg) => ["foreground", bg, 4.5]),
  ...["background", "sidebar", "card", "muted", "accent"].map((bg) => ["muted-foreground", bg, 4.5]),
  ["primary-foreground", "primary", 4.5],
  ...["background", "card", "sidebar"].map((bg) => ["primary", bg, 4.5]),
  ["primary-soft-foreground", "primary-soft", 4.5],
  ["destructive", "background", 4.5],
  ["destructive", "card", 4.5],
  ["destructive-soft-foreground", "destructive-soft", 4.5],
  ["destructive", "destructive-soft", 4.5],
  ...["success", "warning", "info"].flatMap((k) => [[k, `${k}-soft`, 4.5], [k, "card", 4.5], [k, "background", 4.5]]),
  ["secondary-foreground", "secondary", 4.5],
  ["ring", "background", 3],
  ["ring", "sidebar", 3],
  ["ring", "card", 3],
  ["input", "background", 3],
  ["input", "card", 3],
];

const light = tokens(":root");
const dark = { ...light, ...tokens(".dark") };
let failed = 0;
console.log("pair".padEnd(52), "light", " dark", " needs");
for (const [fg, bg, min] of PAIRS) {
  const values = [light, dark].map((set) => ratio(set[fg], set[bg]));
  const bad = values.some((v) => v < min);
  if (bad) failed += 1;
  console.log(`${fg} on ${bg}`.padEnd(52), ...values.map((v) => v.toFixed(2).padStart(5)), String(min).padStart(5),
    bad ? " FAIL" : "");
}
if (failed) {
  console.error(`${failed} pair(s) under the WCAG minimum`);
  process.exit(1);
}
