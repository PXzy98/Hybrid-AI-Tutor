import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { useReturnFocus } from "./dialog";

const Sheet = DialogPrimitive.Root;
const SheetTrigger = DialogPrimitive.Trigger;
const SheetClose = DialogPrimitive.Close;
const SheetTitle = DialogPrimitive.Title;
const SheetDescription = DialogPrimitive.Description;

/** A Radix dialog that slides in from a side: focus is trapped, Escape closes, focus returns to the trigger. */
function SheetContent({ className, children, side = "left", onOpenAutoFocus, onCloseAutoFocus, ...props }:
  React.ComponentProps<typeof DialogPrimitive.Content> & { side?: "left" | "right" }) {
  const { t } = useI18n();
  const focus = useReturnFocus(onOpenAutoFocus, onCloseAutoFocus);
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="animate-in-fade fixed inset-0 z-50 bg-black/40" />
      <DialogPrimitive.Content data-slot="sheet-content" {...focus}
        className={cn("animate-in-fade fixed inset-y-0 z-50 flex flex-col bg-popover text-popover-foreground shadow-float",
          side === "left" ? "left-0 w-72 max-w-[85vw] border-r" : "right-0 w-full max-w-xl border-l", className)}
        {...props}>
        {children}
        <DialogPrimitive.Close aria-label={t("dialog.close")}
          className="absolute top-2.5 right-2.5 inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors outline-hidden hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <X aria-hidden className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle, SheetTrigger };
