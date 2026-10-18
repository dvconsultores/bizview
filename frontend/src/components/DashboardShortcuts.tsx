import { Link } from "react-router";
import type { Dashboard } from "../api/types";
import { useT } from "../i18n";
import { localized } from "../lib/labels";
import { readFavorites, readRecents } from "../lib/dashboardPrefs";
import { dashboardIcon } from "../lib/icons";
import { relativeTime } from "./assistant/AssistantHistory";

const CHIP =
  "inline-flex min-h-tap items-center gap-2 rounded-full border border-line bg-surface px-4 text-sm font-medium text-ink hover:border-line-accent";

/** Favorite (★ in Tableros) and recently opened dashboards of this user on this device; only
 * those still available to them. */
export function DashboardShortcuts({ userId, dashboards }: { userId: number; dashboards: Dashboard[] }) {
  const t = useT();
  const byPath = new Map(dashboards.filter((d) => d.status === "available").map((d) => [d.path, d]));
  const favorites = readFavorites(userId).map((p) => byPath.get(p)).filter((d): d is Dashboard => !!d)
    .map((d) => ({ d, extra: undefined as string | undefined }));
  const recents = readRecents(userId).filter((r) => byPath.has(r.path))
    .map((r) => ({ d: byPath.get(r.path)!, extra: relativeTime(r.at) }));

  const row = (label: string, items: typeof favorites) => (
    <section aria-label={label} className="mb-6">
      <h2 className="mb-2 text-sm font-semibold text-ink-2">{label}</h2>
      <ul className="flex flex-wrap gap-2">
        {items.map(({ d, extra }) => {
          const Icon = dashboardIcon(d.icon);
          return (
            <li key={d.path}>
              <Link to={d.path} className={CHIP}>
                <Icon className="h-4 w-4 text-accent" aria-hidden />
                {localized(d, "name")}
                {extra ? <span className="text-xs font-normal text-ink-muted">{extra}</span> : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );

  return (
    <>
      {favorites.length > 0 ? row(t.home.favorites, favorites) : null}
      {recents.length > 0 ? row(t.home.recents, recents) : null}
    </>
  );
}
