import type { ReactNode } from "react";

import { BrandMark } from "@/components/shell/Sidebar";
import { LanguageSwitch } from "@/i18n";

/** The pages outside the app shell (log in, join): a narrow centred column on the sidebar surface, the brand and
 *  the page h1 above the card, the language switch in the corner. */
export default function AuthLayout({ title, titleId, description, language = true, below, children }: {
  title: string; titleId: string; description?: ReactNode; language?: boolean; below?: ReactNode; children: ReactNode;
}) {
  return (
    <main className="relative flex min-h-dvh flex-col items-center justify-center bg-sidebar px-4 py-16">
      {language && <div className="absolute top-4 right-4"><LanguageSwitch /></div>}
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <BrandMark className="size-10" />
          <div className="space-y-1">
            <h1 id={titleId} className="text-xl font-semibold tracking-tight">{title}</h1>
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </div>
        </div>
        <div className="rounded-xl border bg-card p-6 text-card-foreground">{children}</div>
        {below}
      </div>
    </main>
  );
}
