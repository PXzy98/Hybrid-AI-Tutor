import * as React from "react";

import { cn } from "@/lib/utils";

/** Native select with the shadcn look: keeps the platform picker and full keyboard and screen reader support.
 *  The chevron is the `select-chevron` utility in index.css, so the select stays one native element. */
function Select({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select data-slot="select"
      className={cn("select-chevron h-9 w-full appearance-none rounded-md border border-input bg-background py-1 pr-8 pl-3 text-sm outline-hidden transition-[color,box-shadow,border-color] focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30 disabled:opacity-50 aria-invalid:border-destructive", className)}
      {...props} />
  );
}

export { Select };
