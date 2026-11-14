import * as React from "react";

import { cn } from "@/lib/utils";

/** A placeholder block while data loads. Decorative: the loading text next to it is what assistive technology reads. */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div aria-hidden data-slot="skeleton" className={cn("animate-shimmer rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
