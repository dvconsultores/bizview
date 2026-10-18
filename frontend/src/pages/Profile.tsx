import { ChevronRight, KeyRound, Languages, LogOut, Palette, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CodeChip } from "../components/CodeChip";
import { PageHeader } from "../components/PageHeader";
import { TelegramCard } from "../components/TelegramCard";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { TwoFactorCard } from "../components/TwoFactorCard";
import { RoleBadge } from "../components/UserBadges";
import { useT } from "../i18n";
import { initials } from "../lib/format";

export function Profile() {
  const t = useT();
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  if (!user) return null;

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title={t.profile.title} />

      <Card tone="accent" className="p-5 sm:p-6">
        <div className="flex items-center">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-primary text-xl font-bold text-white" aria-hidden>
            {initials(user.full_name)}
          </div>
          <div className="ml-4 min-w-0">
            <p className="truncate text-lg font-semibold text-ink">{user.full_name}</p>
            <CodeChip className="mt-1 break-all">{user.email}</CodeChip>
            <div className="mt-2">
              <RoleBadge user={user} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="space-y-5 p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Palette className="h-5 w-5" aria-hidden />
          </span>
          <h2 className="text-lg font-semibold text-ink">{t.theme.title}</h2>
        </div>
        <ThemeSwitcher />
        <p className="text-sm text-ink-muted">{t.theme.hint}</p>
      </Card>

      <Card className="space-y-5 p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Languages className="h-5 w-5" aria-hidden />
          </span>
          <h2 className="text-lg font-semibold text-ink">{t.language.title}</h2>
        </div>
        <LanguageSwitcher />
        <p className="text-sm text-ink-muted">{t.language.hint}</p>
      </Card>

      <Card className="p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </span>
          <h2 className="text-lg font-semibold text-ink">{t.profile.security}</h2>
        </div>
        <Link to="/cambiar-clave" className="-mx-2 mt-2 flex min-h-tap items-center rounded-xl px-2 py-2 hover:bg-subtle">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <KeyRound className="h-5 w-5" aria-hidden />
          </span>
          <span className="ml-3 flex-1 font-medium text-ink">{t.profile.changePassword}</span>
          <ChevronRight className="h-5 w-5 text-ink-faint" aria-hidden />
        </Link>
      </Card>

      <TwoFactorCard />

      <TelegramCard />

      <Button variant="secondary" block icon={<LogOut className="h-5 w-5" aria-hidden />} loading={loggingOut} onClick={handleLogout}>
        {t.nav.signOut}
      </Button>

    </div>
  );
}
