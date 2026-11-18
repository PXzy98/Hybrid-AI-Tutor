import { Toaster as Sonner } from "sonner";

import { useIsDark } from "@/components/theme";

/** Toasts for short confirmations ("Copied"). Mounted once by the app; the colours come from the theme tokens. */
export function Toaster() {
  const dark = useIsDark();
  return (
    <Sonner theme={dark ? "dark" : "light"} position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "animate-in-up !rounded-lg !border !border-border !bg-popover !text-popover-foreground !shadow-float !text-sm",
          description: "!text-muted-foreground",
        },
      }} />
  );
}

export { toast } from "sonner";
