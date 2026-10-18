import { Check, Clock, LayoutDashboard, LayoutGrid, Search, Star, Table2 } from "lucide-react";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { localized } from "../lib/labels";
import {
  matches,
  readFavorites,
  readView,
  toggleFavorite,
  writeView,
  type HomeView,
} from "../lib/dashboardPrefs";
import { dashboardIcon } from "../lib/icons";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

const ICON_BOX = "inline-flex shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent";

function initialView(): HomeView {
  const stored = readView();
  if (stored) return stored;
  const phone = typeof window.matchMedia === "function" && window.matchMedia("(max-width: 639px)").matches;
  return phone ? "table" : "grid";
}

function StarButton({ d, on, onToggle, className }: {
  d: Dashboard; on: boolean; onToggle: () => void; className: string;
}) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={on}
      aria-label={on ? t.home.removeFavorite(localized(d, "name")) : t.home.addFavorite(localized(d, "name"))}
      className={`inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl text-ink-muted hover:bg-subtle hover:text-accent ${className}`}
    >
      <Star className={`h-5 w-5 ${on ? "fill-current text-accent" : ""}`} aria-hidden />
    </button>
  );
}

function SoonBadge() {
  const t = useT();
  return <Badge tone="amber" icon={<Clock className="h-3.5 w-3.5" aria-hidden />}>{t.home.comingSoon}</Badge>;
}

/** One dashboard as a compact card; the link's accessible name is the dashboard's name. */
function Card({ d, favorite, onToggle }: { d: Dashboard; favorite: boolean; onToggle: () => void }) {
  const titleId = useId();
  const Icon = dashboardIcon(d.icon);
  const available = d.status === "available";
  const shape = "flex h-full min-h-tap items-start gap-3 rounded-card border border-line bg-surface p-4 pr-14";
  const body = (
    <>
      <span className={`${ICON_BOX} h-9 w-9`}><Icon className="h-5 w-5" aria-hidden /></span>
      <span className="min-w-0">
        <span id={titleId} className="block truncate font-semibold text-ink">{localized(d, "name")}</span>
        <span className="block truncate text-sm text-ink-muted">{localized(d, "description")}</span>
        {available ? null : <span className="mt-2 block"><SoonBadge /></span>}
      </span>
    </>
  );
  return (
    <li className="relative">
      {available ? (
        <Link to={d.path} aria-labelledby={titleId}
          className={`${shape} transition-colors hover:border-line-accent hover:shadow-raised`}>{body}</Link>
      ) : (
        <div aria-disabled="true" className={`${shape} cursor-not-allowed opacity-75`}>{body}</div>
      )}
      {available ? (
        <StarButton d={d} on={favorite} onToggle={onToggle} className="absolute right-2 top-2" />
      ) : null}
    </li>
  );
}

function Row({ d, favorite, onToggle }: { d: Dashboard; favorite: boolean; onToggle: () => void }) {
  const t = useT();
  const Icon = dashboardIcon(d.icon);
  const available = d.status === "available";
  const name = (
    <span className="flex min-w-0 items-center gap-3">
      <span className={`${ICON_BOX} h-8 w-8`}><Icon className="h-4 w-4" aria-hidden /></span>
      <span className="truncate font-medium">{localized(d, "name")}</span>
    </span>
  );
  return (
    <tr className="hover:bg-subtle">
      <th scope="row" className="max-w-0 px-4 py-2 text-left font-normal">
        {available ? (
          <Link to={d.path} className="flex min-h-tap items-center text-ink hover:text-accent">{name}</Link>
        ) : (
          <span aria-disabled="true" className="flex min-h-tap items-center text-ink opacity-75">{name}</span>
        )}
      </th>
      <td className="hidden max-w-0 truncate px-4 py-2 text-sm text-ink-muted md:table-cell">{localized(d, "description")}</td>
      <td className="whitespace-nowrap px-4 py-2">
        {available ? (
          <Badge tone="green" icon={<Check className="h-3.5 w-3.5" aria-hidden />}>{t.home.available}</Badge>
        ) : <SoonBadge />}
      </td>
      <td className="w-14 px-2 py-1 text-right">
        {available ? <StarButton d={d} on={favorite} onToggle={onToggle} className="" /> : null}
      </td>
    </tr>
  );
}

/** Dashboards the user can open (Tableros): search (name or description, case/accent-insensitive),
 * grid or table, and ★ favorites shown on Inicio. Favorites and the view are kept per user and
 * device. */
export function DashboardCatalog({ heading }: {
  /** The left part of the toolbar card (it holds the page's h1). */
  heading: (count: number | null) => ReactNode;
}) {
  const t = useT();
  const { user } = useAuth();
  const [dashboards, setDashboards] = useState<Dashboard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<HomeView>(initialView);
  const [favorites, setFavorites] = useState<string[]>(() => (user ? readFavorites(user.id) : []));
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const searchId = useId();

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

  const all = dashboards ?? [];
  const shown = all.filter((d) => matches(d, query));
  const switchView = (v: HomeView) => {
    setView(v);
    writeView(v);
  };
  const toggle = (path: string) => setFavorites(toggleFavorite(user.id, path));
  const viewButton = (v: HomeView, label: string, Icon: typeof Table2) => (
    <button type="button" onClick={() => switchView(v)} aria-pressed={view === v} aria-label={label} title={label}
      className={`inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl ${
        view === v ? "bg-accent-soft text-accent" : "text-ink-muted hover:bg-subtle"}`}>
      <Icon className="h-5 w-5" aria-hidden />
    </button>
  );
  return (
    <div>
      <section className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-card border border-line bg-surface px-5 py-4">
        <div className="min-w-0">{heading(dashboards ? dashboards.length : null)}</div>
        <div className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
          <label htmlFor={searchId} className="sr-only">{t.home.search}</label>
          <div className="relative min-w-0 flex-1 sm:w-72 sm:flex-none">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" aria-hidden />
            <input id={searchId} type="search" value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder={t.home.searchPlaceholder}
              className="min-h-tap w-full rounded-xl border-0 bg-field py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-field-focus" />
          </div>
          <div role="group" aria-label={t.home.viewLabel} className="flex shrink-0 gap-1">
            {viewButton("grid", t.home.gridView, LayoutGrid)}
            {viewButton("table", t.home.tableView, Table2)}
          </div>
        </div>
      </section>

      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={retry}>{t.common.retry}</Button>}>
          {error}
        </Alert>
      ) : dashboards === null ? (
        <div role="status" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          <span className="sr-only">{t.common.loading}</span>
          {[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-card bg-fill/70" />)}
        </div>
      ) : dashboards.length === 0 ? (
        <EmptyState icon={<LayoutDashboard className="h-7 w-7" aria-hidden />} title={t.home.empty} />
      ) : (
        <>
          <h2 className="mb-3 text-sm font-semibold text-ink-2">{t.home.all(shown.length)}</h2>
          {shown.length === 0 ? (
            <p className="rounded-card border border-line bg-surface p-6 text-center text-sm text-ink-muted">
              {t.home.noMatch(query.trim())}
            </p>
          ) : view === "grid" ? (
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {shown.map((d) => (
                <Card key={d.code} d={d} favorite={favorites.includes(d.path)} onToggle={() => toggle(d.path)} />
              ))}
            </ul>
          ) : (
            <div className="overflow-hidden rounded-card border border-line bg-surface">
              <table className="w-full table-fixed text-sm">
                <caption className="sr-only">{t.home.all(shown.length)}</caption>
                <thead className="border-b border-line bg-canvas text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <tr>
                    <th scope="col" className="px-4 py-3">{t.home.colDashboard}</th>
                    <th scope="col" className="hidden px-4 py-3 md:table-cell">{t.home.colDescription}</th>
                    <th scope="col" className="w-36 px-4 py-3">{t.home.colStatus}</th>
                    <th scope="col" className="w-14 px-2 py-3"><span className="sr-only">{t.home.colFavorite}</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {shown.map((d) => (
                    <Row key={d.code} d={d} favorite={favorites.includes(d.path)} onToggle={() => toggle(d.path)} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
