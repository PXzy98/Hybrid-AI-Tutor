import { ChevronsUpDown, KeyRound, LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { api, type Me } from "@/api/endpoints";
import { useResetSession } from "@/auth";
import { useTheme, type ThemePref } from "@/components/theme";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup,
  DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LANGS, useI18n, type Lang } from "@/i18n";
import { cn } from "@/lib/utils";

const THEMES: { id: ThemePref; label: "theme.light" | "theme.dark" | "theme.system" }[] = [
  { id: "light", label: "theme.light" }, { id: "dark", label: "theme.dark" }, { id: "system", label: "theme.system" },
];

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : name.slice(0, 2)).toUpperCase();
}

/** The account button at the bottom of the sidebar: language, theme, password and log out. */
export default function UserMenu({ me, compact = false }: { me: Me; compact?: boolean }) {
  const { t, lang, setLang } = useI18n();
  const [theme, setTheme] = useTheme();
  const navigate = useNavigate();
  const resetSession = useResetSession();

  async function logout() {
    await api.logout().catch(() => undefined);
    resetSession(null);
    navigate("/login", { replace: true });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn("flex min-w-0 items-center gap-2.5 rounded-md text-left text-sm outline-hidden hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-accent",
          compact ? "h-9 px-1.5" : "h-11 w-full px-2")}>
        <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary-soft-foreground">
          {initials(me.display_name)}
        </span>
        <span className={cn("min-w-0 flex-1 truncate font-medium", compact && "sr-only")}>
          <span className="sr-only">{t("nav.account")}{" "}</span>{me.display_name}
        </span>
        {!compact && <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-muted-foreground" />}
      </DropdownMenuTrigger>
      <DropdownMenuContent align={compact ? "end" : "start"} side={compact ? "bottom" : "top"} className="w-64">
        <DropdownMenuLabel className="truncate text-sm font-medium text-foreground">{me.display_name}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup aria-label={t("lang.label")}>
          <DropdownMenuLabel>{t("lang.label")}</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={lang} onValueChange={(v) => setLang(v as Lang)}>
            {LANGS.map((l) => <DropdownMenuRadioItem key={l.id} value={l.id} lang={l.id}>{l.label}</DropdownMenuRadioItem>)}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as ThemePref)}>
          {THEMES.map((x) => <DropdownMenuRadioItem key={x.id} value={x.id}>{t(x.label)}</DropdownMenuRadioItem>)}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/change-password"><KeyRound aria-hidden />{t("nav.changePassword")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void logout()}><LogOut aria-hidden />{t("nav.logout")}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
