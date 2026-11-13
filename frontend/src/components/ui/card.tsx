import * as React from "react";

import { cn } from "@/lib/utils";

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card" className={cn("flex flex-col gap-4 rounded-xl border bg-card py-5 text-card-foreground shadow-sm", className)} {...props} />;
}
function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-header" className={cn("flex flex-col gap-1.5 px-5", className)} {...props} />;
}
// A div (as in current shadcn/ui) that is announced as a level 3 heading: cards sit below the page's h1 and the
// tab's h2. A page that needs another level puts its own heading element in the header instead of a CardTitle.
function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-title" role="heading" aria-level={3} className={cn("leading-none font-semibold", className)} {...props} />;
}
function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p data-slot="card-description" className={cn("text-sm text-muted-foreground", className)} {...props} />;
}
function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("px-5", className)} {...props} />;
}

export { Card, CardContent, CardDescription, CardHeader, CardTitle };
