import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, Info, TriangleAlert } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border px-4 py-3 text-sm", {
  variants: {
    variant: {
      default: "bg-card text-card-foreground",
      info: "border-info-border bg-info-soft text-foreground",
      warning: "border-warning-border bg-warning-soft text-foreground",
      destructive: "border-destructive/40 bg-destructive-soft text-destructive-soft-foreground",
    },
  },
  defaultVariants: { variant: "default" },
});

const ICONS = {
  default: [Info, "text-muted-foreground"],
  info: [Info, "text-info"],
  warning: [TriangleAlert, "text-warning"],
  destructive: [CircleAlert, ""],
} as const;

/** `icon` puts the variant's icon before the text (decorative: the text carries the meaning). */
function Alert({ className, variant, icon = false, children, ...props }:
  React.ComponentProps<"div"> & VariantProps<typeof alertVariants> & { icon?: boolean }) {
  const [Icon, tone] = ICONS[variant ?? "default"];
  if (!icon) return <div data-slot="alert" className={cn(alertVariants({ variant }), className)} {...props}>{children}</div>;
  return (
    <div data-slot="alert" className={cn(alertVariants({ variant }), "flex items-start gap-2.5", className)} {...props}>
      <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", tone)} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export { Alert };
