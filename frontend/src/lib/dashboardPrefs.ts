/** Home page preferences per user and device (favorites, recently opened, grid/list view).
 * Browser storage only: it can be unavailable (private mode), so every access is guarded. */
export type HomeView = "grid" | "table";
export interface Recent {
  path: string;
  at: string;
}

const FAVORITES = (userId: number) => `bizview.home.favorites.${userId}`;
const RECENTS = (userId: number) => `bizview.home.recents.${userId}`;
const VIEW = "bizview.home.view";
const MAX_RECENTS = 5;

function load(key: string): unknown {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, typeof value === "string" ? value : JSON.stringify(value));
  } catch {
    /* storage unavailable: the preference lasts until the page is reloaded */
  }
}

export function readFavorites(userId: number): string[] {
  const v = load(FAVORITES(userId));
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

export function toggleFavorite(userId: number, path: string): string[] {
  const current = readFavorites(userId);
  const next = current.includes(path) ? current.filter((p) => p !== path) : [...current, path];
  save(FAVORITES(userId), next);
  return next;
}

export function readRecents(userId: number): Recent[] {
  const v = load(RECENTS(userId));
  return Array.isArray(v)
    ? v.filter((x): x is Recent => !!x && typeof x.path === "string" && typeof x.at === "string")
        .slice(0, MAX_RECENTS)
    : [];
}

export function recordRecent(userId: number, path: string, now = new Date()): void {
  const others = readRecents(userId).filter((r) => r.path !== path);
  save(RECENTS(userId), [{ path, at: now.toISOString() }, ...others].slice(0, MAX_RECENTS));
}

export function readView(): HomeView | null {
  try {
    const v = localStorage.getItem(VIEW);
    if (v === "list") return "table";   // stored before the table view existed
    return v === "grid" || v === "table" ? v : null;
  } catch {
    return null;
  }
}

export function writeView(v: HomeView): void {
  save(VIEW, v);
}

const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Case- and accent-insensitive search on name or description. */
export function matches(
  d: { name: string; description: string; name_en?: string; description_en?: string },
  query: string,
): boolean {
  const q = fold(query.trim());
  return (
    !q ||
    fold(d.name).includes(q) ||
    fold(d.name_en ?? "").includes(q) ||
    fold(d.description).includes(q) ||
    fold(d.description_en ?? "").includes(q)
  );
}
