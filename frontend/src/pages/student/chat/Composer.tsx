import { ArrowUp, Cloud, Square } from "lucide-react";
import { useLayoutEffect, useRef, type FormEvent, type Ref } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/i18n";

const MAX_HEIGHT = 240;  // about 8 lines, then the field scrolls

type Props = {
  ref?: Ref<HTMLTextAreaElement>;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: FormEvent | { preventDefault: () => void }) => void;
  onStop: () => void;
  pending: boolean;
  scopeLabel: string;
  localOnly: boolean;
};

/** The floating question box. Enter sends, Shift+Enter makes a new line; nothing is sent during an IME composition.
 *  While an answer runs the send button becomes Stop. */
export default function Composer({ ref, value, onChange, onSubmit, onStop, pending, scopeLabel, localOnly }: Props) {
  const { t } = useI18n();
  const field = useRef<HTMLTextAreaElement | null>(null);

  // grow with the text (no dependency): measure the content height after each change
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    if (el.scrollHeight) el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  function setRefs(el: HTMLTextAreaElement | null) {
    field.current = el;
    if (typeof ref === "function") ref(el);
    else if (ref) ref.current = el;
  }

  return (
    <>
      <form onSubmit={onSubmit}
            className="rounded-2xl border bg-card shadow-float transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/30">
        <label htmlFor="question" className="sr-only">{t("chat.question")}</label>
        <textarea id="question" ref={setRefs} rows={1} placeholder={t("chat.placeholder")} value={value}
                  onChange={(e) => onChange(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) onSubmit(e); }}
                  style={{ maxHeight: MAX_HEIGHT }}
                  className="block w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 pb-1 text-[0.9375rem] leading-7 outline-none placeholder:text-muted-foreground" />
        <div className="flex items-center gap-2 px-3 pt-1 pb-2.5">
          <Badge variant="secondary" className="max-w-[60%] truncate font-normal">{scopeLabel}</Badge>
          <div className="ml-auto">
            {pending ? (
              <Tooltip content={t("chat.stop")} side="top">
                <Button type="button" size="icon" className="rounded-full" aria-label={t("chat.stop")} onClick={onStop}>
                  <Square aria-hidden className="size-3.5 fill-current" />
                </Button>
              </Tooltip>
            ) : (
              <Tooltip content={t("chat.send")} side="top">
                <Button type="submit" size="icon" className="rounded-full" aria-label={t("chat.send")} disabled={!value.trim()}>
                  <ArrowUp aria-hidden />
                </Button>
              </Tooltip>
            )}
          </div>
        </div>
      </form>
      {!localOnly && <CloudNotice />}
    </>
  );
}

/** T8: the student is told before sending that a cloud model may see the (filtered) question. Always visible, never
 *  dismissible. */
export function CloudNotice() {
  const { t, lang } = useI18n();
  return (
    <div role="note" className="mt-2 space-y-0.5 px-2 text-xs text-muted-foreground">
      <p className="flex gap-1.5"><Cloud aria-hidden className="mt-0.5 size-3.5 shrink-0" /><span>{t("chat.cloudNotice")}</span></p>
      {lang !== "en" && <p className="pl-5">{t("chat.englishOnly")}</p>}
    </div>
  );
}
