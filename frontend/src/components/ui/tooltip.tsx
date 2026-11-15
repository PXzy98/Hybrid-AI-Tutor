import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as React from "react";

import { cn } from "@/lib/utils";

/** A visual label for an icon-only control. It never replaces the control's aria-label. Each tooltip brings its own
 *  provider, so a component works without a provider higher up (unit tests render pages on their own). */
function Tooltip({ content, children, side = "bottom" }:
  { content: React.ReactNode; children: React.ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content side={side} sideOffset={6}
            className={cn("animate-in-fade z-50 max-w-xs rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-float")}>
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export { Tooltip };
