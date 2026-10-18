import { DashboardCatalog } from "../components/DashboardCatalog";
import { useT } from "../i18n";

/** Tableros: every dashboard the user can open, as a grid or a table, with search. */
export function Dashboards() {
  const t = useT();
  return (
    <div>
      <DashboardCatalog
        heading={(count) => (
          <>
            <h1 className="text-xl font-bold tracking-tight text-ink">{t.home.title}</h1>
            <p className="text-sm text-ink-muted">
              {t.home.pageSubtitle}
              {count !== null ? ` · ${t.home.count(count)}` : ""}
            </p>
          </>
        )}
      />
    </div>
  );
}
