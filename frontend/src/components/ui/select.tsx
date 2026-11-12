import * as React from "react";

import { cn } from "@/lib/utils";

/** Native select with the shadcn look: keeps the platform picker and full keyboard and screen reader support. */
function Select({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select data-slot="select"
      className={cn("h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50", className)}
      {...props} />
  );
}

export { Select };
