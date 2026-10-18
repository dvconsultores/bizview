import { ArrowRight, LayoutDashboard } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { DashboardShortcuts } from "../components/DashboardShortcuts";
import { EmptyState } from "../components/EmptyState";
import { OverviewTiles } from "../components/OverviewTiles";
import { WelcomeBanner } from "../components/WelcomeBanner";
import { useT } from "../i18n";
import { firstName } from "../lib/format";

/** Inicio: greeting, counters, favorite and recent dashboards; every dashboard is in Tableros. */
export function Home() {
  const t = useT();
  const { user } = useAuth();
  const [dashboards, setDashboards] = useState<Dashboard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setDashboards(null);
    api
      .get<{ items: Dashboard[] }>("/api/dashboards")
      .then((data) => !cancelled && setDashboards(data.items))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (!user) return null;

  return (
    <div>
      <WelcomeBanner name={firstName(user.full_name)} chip={t.home.title} subtitle={t.home.subtitle} className="mb-6" />
      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={retry}>{t.common.retry}</Button>}>
          {error}
        </Alert>
      ) : (
        <>
          <OverviewTiles dashboards={dashboards} />
          {dashboards && dashboards.length === 0 ? (
            <EmptyState
              icon={<LayoutDashboard className="h-7 w-7" aria-hidden />}
              title={t.home.empty}
            />
          ) : dashboards ? (
            <>
              <DashboardShortcuts userId={user.id} dashboards={dashboards} />
              <Link to="/tableros"
                className="inline-flex min-h-tap items-center gap-2 font-semibold text-accent hover:underline">
                {t.home.seeAll}
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
