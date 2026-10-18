import { Ban, Clock, Home as HomeIcon, LayoutDashboard } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { Dashboard } from "../api/types";
import { Alert } from "../components/Alert";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { ButtonLink } from "../components/Button";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { Spinner } from "../components/Spinner";
import { useT } from "../i18n";
import { localized } from "../lib/labels";
import { useAuth } from "../auth/AuthContext";
import { recordRecent } from "../lib/dashboardPrefs";

function Panel({ icon, tone, title, text }: { icon: ReactNode; tone: string; title: string; text?: string }) {
  const t = useT();
  return (
    <Card className="p-8 text-center">
      <div className={`mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full ${tone}`}>{icon}</div>
      <h1 className="text-2xl font-bold text-ink">{title}</h1>
      {text ? <p className="mx-auto mt-2 max-w-md text-ink-muted">{text}</p> : null}
      <ButtonLink to="/" className="mt-6" icon={<HomeIcon className="h-5 w-5" aria-hidden />}>
        {t.notFound.home}
      </ButtonLink>
    </Card>
  );
}

/** Server-checked entry to a dashboard: refuses typed URLs without access (FR-021). */
export function DashboardGate() {
  const t = useT();
  const { code = "" } = useParams();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const { user } = useAuth();
  const loaded = dashboard !== null;

  useEffect(() => {
    if (loaded && user) recordRecent(user.id, `/d/${code}`);   // home page "Recientes"
  }, [loaded, user, code]);

  useEffect(() => {
    let cancelled = false;
    setDashboard(null);
    setError(null);
    api
      .get<Dashboard>(`/api/dashboards/${encodeURIComponent(code)}`)
      .then((d) => !cancelled && setDashboard(d))
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err : new ApiError(0, "error", t.common.unexpected));
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    let panel: ReactNode;
    if (error.status === 403 && error.code === "coming_soon") {
      panel = <Panel icon={<Clock className="h-8 w-8" aria-hidden />} tone="bg-warning-soft text-warning" title={t.gate.comingSoon} text={t.gate.comingSoonText} />;
    } else if (error.status === 403) {
      panel = <Panel icon={<Ban className="h-8 w-8" aria-hidden />} tone="bg-danger-soft text-danger" title={t.gate.forbidden} text={t.gate.forbiddenText} />;
    } else if (error.status === 404) {
      panel = <Panel icon={<LayoutDashboard className="h-8 w-8" aria-hidden />} tone="bg-surface-2 text-ink-muted" title={t.gate.notFound} text={t.notFound.text} />;
    } else {
      panel = <Alert tone="error">{error.message}</Alert>;
    }
    return (
      <div>
        <Breadcrumbs back="/" items={[]} />
        {panel}
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="flex justify-center py-16 text-accent" role="status">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  // Reports of the applied workspace (feature 005) render at /r/<id>.
  if (dashboard.path !== `/d/${dashboard.code}`) return <Navigate to={dashboard.path} replace />;

  return (
    <div>
      <Breadcrumbs back="/" items={[{ label: t.nav.home, to: "/" }, { label: localized(dashboard, "name") }]} />
      <PageHeader title={localized(dashboard, "name")} subtitle={localized(dashboard, "description")} />
      <Alert tone="info">{t.gate.placeholder}</Alert>
    </div>
  );
}
