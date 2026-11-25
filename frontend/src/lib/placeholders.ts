import type { T } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

const KNOWN = new Set(["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "USERNAME", "HEALTH_CARD", "HEALTH_DETAIL"]);

/** Stored conversations hold the sanitized text, where the privacy filter left markers like `<PERSON_1>`. In the
 *  student's view of past turns they read as a neutral token ("[name]") instead of raw markup. Display only. */
export function readablePlaceholders(text: string, t: T): string {
  return text.replace(/<([A-Z][A-Z_]*)_\d+>/g, (_, type: string) =>
    t(KNOWN.has(type) ? (`placeholder.${type}` as MessageKey) : "placeholder.other"));
}
