import { useAuth } from "../../auth/AuthContext";
import { AIPill } from "../../components/assistant/AIPill";
import { HubCard } from "../../components/HubCard";
import { PageHeader } from "../../components/PageHeader";
import { useAIHealth } from "../../api/ai";
import { useT } from "../../i18n";
import { ADMIN_TILES } from "./adminTiles";

export function AdminHome() {
  const t = useT();
  const { user } = useAuth();
  const isSuperuser = Boolean(user?.is_superuser);
  const visible = ADMIN_TILES.filter((e) => !e.superOnly || isSuperuser);
  const health = useAIHealth();

  return (
    <div>
      {/* 035: the AI state is visible before opening the page, so a dead provider is never a surprise. */}
      <PageHeader title={t.nav.admin} subtitle={t.admin.home.subtitle} badge={<AIPill health={health} compact={false} />} />
      {/* The counters live on the home page (Inicio). */}

      <h2 className="mb-3 text-lg font-semibold text-ink-2">{t.admin.home.sections}</h2>

      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {visible.map(({ to, title, text, icon: Icon }) => (
          <li key={to}>
            <HubCard
              to={to}
              title={title(t)}
              description={text(t)}
              icon={<Icon className="h-5 w-5" aria-hidden />}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
