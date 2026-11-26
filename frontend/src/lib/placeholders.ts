import type { T } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

const KNOWN = new Set(["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "USERNAME", "HEALTH_CARD", "HEALTH_DETAIL"]);

// the exact form the filter writes, for any type
const EXACT = /<([A-Z][A-Z_]*)_\d+>/g;
// forms the model may change a marker into, as the backend's restore() accepts them (lower case, spaces, square
// brackets); matched for the known types only, so ordinary text such as `a[i_1]` is left alone
const LOOSE = /[<[]\s*([A-Za-z]+(?:_[A-Za-z]+)*)_\d+\s*[>\]]/g;
// fenced blocks and inline code: shown as written
const CODE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/;

/** Stored conversations hold the sanitized text, where the privacy filter left markers like `<PERSON_1>`. In the
 *  student's view of past turns they read as a neutral token ("[name]") instead of raw markup. Code is left as
 *  written. Display only. */
export function readablePlaceholders(text: string, t: T): string {
  const token = (type: string) => t(KNOWN.has(type) ? (`placeholder.${type}` as MessageKey) : "placeholder.other");
  return text.split(CODE).map((part, i) => i % 2 === 1 ? part : part
    .replace(EXACT, (_, type: string) => token(type))
    .replace(LOOSE, (m, type: string) => KNOWN.has(type.toUpperCase()) ? token(type.toUpperCase()) : m)).join("");
}
