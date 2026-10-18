import { Database, LayoutDashboard, Users, Workflow } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { StatTile } from "./StatTile";

type Count = number | null | "error";

interface Stats {
  users: Count;
  activeUsers: Count;
  sources: Count;
  connectedSources: Count;
  integrations: Count;
  failedIntegrations: Count;
}

interface Overview {
  users: number;
  active_users: number;
  sources?: number;
  connected_sources?: number;
  integrations?: number;
  failed_integrations?: number;
}

const EMPTY: Stats = {
  users: null, activeUsers: null, sources: null, connectedSources: null,
  integrations: null, failedIntegrations: null,
};

/** Counters on the home page: dashboards for everyone; users for administrators; data sources
 * and integrations for the super user (each tile hides itself if its data cannot be read). */
export function OverviewTiles({ dashboards }: { dashboards: Dashboard[] | null }) {
  const t = useT();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isSuperuser = Boolean(user?.is_superuser);
  const [stats, setStats] = useState<Stats>(EMPTY);

  // One request for every counter (each request to the server costs a round trip).
  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    api.get<Overview>("/api/admin/overview")
      .then((o) => !cancelled && setStats({
        users: o.users, activeUsers: o.active_users,
        sources: o.sources ?? "error", connectedSources: o.connected_sources ?? null,
        integrations: o.integrations ?? "error", failedIntegrations: o.failed_integrations ?? null,
      }))
      .catch(() => !cancelled && setStats({ ...EMPTY, users: "error", sources: "error", integrations: "error" }));
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const value = (c: Count) => (c === null || c === "error" ? "—" : c);
  const known = (c: Count): c is number => typeof c === "number";
  const available = dashboards?.filter((d) => d.status === "available").length;

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label={t.home.title}
        value={dashboards === null ? "—" : dashboards.length}
        icon={<LayoutDashboard className="h-5 w-5" aria-hidden />}
        footnote={available === undefined ? undefined : t.home.availableCount(available)}
      />
      {isAdmin && stats.users !== "error" ? (
        <StatTile
          label={t.nav.users}
          value={value(stats.users)}
          icon={<Users className="h-5 w-5" aria-hidden />}
          footnote={known(stats.activeUsers) ? t.home.activeCount(stats.activeUsers) : undefined}
        />
      ) : null}
      {isSuperuser && stats.sources !== "error" ? (
        <StatTile
          label={t.home.tiles.sources}
          value={value(stats.sources)}
          icon={<Database className="h-5 w-5" aria-hidden />}
          footnote={known(stats.connectedSources) ? t.home.connectedCount(stats.connectedSources) : undefined}
        />
      ) : null}
      {isSuperuser && stats.integrations !== "error" ? (
        <StatTile
          label={t.home.tiles.integrations}
          value={value(stats.integrations)}
          icon={<Workflow className="h-5 w-5" aria-hidden />}
          footnote={known(stats.failedIntegrations)
            ? (stats.failedIntegrations > 0 ? t.home.failuresCount(stats.failedIntegrations) : t.home.noFailures)
            : undefined}
        />
      ) : null}
    </div>
  );
}
