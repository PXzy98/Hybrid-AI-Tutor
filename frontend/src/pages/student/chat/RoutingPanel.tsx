import { Check, ChevronRight, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import RoutingProgress, { type RoutingTrace } from "@/components/RoutingProgress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useI18n } from "@/i18n";

/** Seconds since the question was sent, updated once a second while the answer runs. */
function useElapsed(trace: RoutingTrace) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!trace.running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [trace.running]);
  return Math.max(0, (trace.finishedAt ?? now) - trace.startedAt) / 1000;
}

/** The routing steps of one answer: a quiet pill above it, collapsed by default and not announced. */
export default function RoutingPanel({ trace }: { trace: RoutingTrace }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const seconds = useElapsed(trace);
  const Icon = trace.running ? Loader2 : trace.error ? X : Check;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors outline-hidden hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
        <Icon aria-hidden className={`size-3.5 ${trace.running ? "animate-spin motion-reduce:animate-none" : trace.error ? "text-destructive" : "text-success"}`} />
        {t("chat.routingSteps")}
        <span aria-hidden className="tabular-nums">· {trace.running ? `${t("routing.running")} ${Math.floor(seconds)}` : seconds.toFixed(1)} s</span>
        <ChevronRight aria-hidden className={`size-3.5 transition-transform motion-reduce:transition-none ${open ? "rotate-90" : ""}`} />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2"><RoutingProgress trace={trace} /></CollapsibleContent>
    </Collapsible>
  );
}
