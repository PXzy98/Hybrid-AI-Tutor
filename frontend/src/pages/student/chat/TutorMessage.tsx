import { Cloud, Copy, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import type { AskResponse } from "@/api/endpoints";
import CheckCard from "@/components/CheckCard";
import Markdown from "@/components/LazyMarkdown";
import { BrandMark } from "@/components/shell/Sidebar";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { Tooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/i18n";
import Sources from "./Sources";

/** The frame every tutor message shares (streaming, stored history, final answer), so the final answer replaces the
 *  streamed text without a layout jump. No bubble: the answer takes the reading column. */
export function TutorFrame({ route, children }: { route?: ReactNode; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <article className="min-w-0 space-y-3">
      <div className="flex items-center gap-2">
        <BrandMark className="size-6" />
        <span className="text-sm font-medium">{t("chat.tutor")}</span>
        {route}
      </div>
      {children}
    </article>
  );
}

/** Local or cloud, on every live answer: text and icon, the hint in a tooltip that keyboard focus also opens. */
export function RouteLabel({ target }: { target: string }) {
  const { t } = useI18n();
  const local = target === "local";
  return (
    <Tooltip content={t(local ? "chat.localHint" : "chat.cloudHint")}>
      <button type="button" className="rounded-full outline-hidden focus-visible:ring-2 focus-visible:ring-ring">
        <Badge variant={local ? "success" : "info"} data-route={target}>
          {local ? <ShieldCheck aria-hidden /> : <Cloud aria-hidden />}
          {t(local ? "chat.local" : "chat.cloud")}
        </Badge>
      </button>
    </Tooltip>
  );
}

export function CopyAnswer({ text }: { text: string }) {
  const { t } = useI18n();
  function copy() {
    navigator.clipboard?.writeText(text).then(() => toast(t("chat.copied"))).catch(() => undefined);
  }
  return (
    <div className="flex items-center gap-1">
      <Tooltip content={t("chat.copy")}>
        <Button type="button" variant="ghost" size="icon-sm" className="text-muted-foreground" aria-label={t("chat.copy")} onClick={copy}>
          <Copy aria-hidden />
        </Button>
      </Tooltip>
    </div>
  );
}

export const answerBody = "text-[0.9375rem] leading-7";

export default function TutorMessage({ reply, courseId }: { reply: AskResponse; courseId: number }) {
  const { t } = useI18n();
  return (
    <TutorFrame route={<RouteLabel target={reply.route_target} />}>
      <div className={answerBody}><Markdown>{reply.answer}</Markdown></div>
      {!!reply.warnings?.length && (
        <Alert variant="warning" icon>
          <ul className="space-y-0.5">{reply.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </Alert>
      )}
      {!!reply.sources?.length && <Sources sources={reply.sources} />}
      {reply.next_kc && (
        <p className="text-sm text-muted-foreground">{t("chat.suggestedNext")} <strong className="font-medium text-foreground">{reply.next_kc.name}</strong></p>
      )}
      <CopyAnswer text={reply.answer} />
      {reply.check_item && <CheckCard courseId={courseId} item={reply.check_item} />}
    </TutorFrame>
  );
}
