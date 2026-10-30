import { useState } from "react";
import type { ReportImageSet } from "../../api/types";
import { roleAt, surfaceClass } from "./layoutRoles";

/** The file stem the server looks up: the same rule as `app/projects/assets.normalise_key`. */
const UNSAFE = /[^A-Za-z0-9._-]+/g;

export function imageKey(value: unknown): string {
  const raw = value === null || value === undefined ? "" : String(value).trim();
  return raw.replace(UNSAFE, "_").replace(/^[._-]+|[._-]+$/g, "");
}

/** Stable colour for the initial circle: the same key always gets the same palette role. */
function roleFor(key: string) {
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) hash = (hash * 31 + key.charCodeAt(i)) % 100000;
  return roleAt([], hash);
}

const CACHED = /^[0-9a-f]{64}\.(png|jpe?g|webp)$/;
const ABSOLUTE = /^https?:\/\//i;

/** The image URL of one row: the cached file when the worker already fetched the value, the raw
 * address otherwise (a failed fetch keeps it, and the browser's `onError` ends in the fallback). */
export function imageSrc(set: ReportImageSet, value: unknown): string | null {
  const raw = value === null || value === undefined ? "" : String(value).trim();
  if (raw === "") return null;
  if (CACHED.test(raw)) return set.cached_url ? `${set.cached_url}${raw}` : null;
  return ABSOLUTE.test(raw) ? raw : null;
}

/** Feature 044: the image of a row key in a declared set — 20 px in a table cell, 40 px in a tile.
 *
 * The URL comes from the payload (`images.<set>.url`), so only the key is appended and a file name
 * is never guessed. A key with no file, a broken image and `fallback: none` all end in nothing
 * drawn; `fallback: initial` draws a circle with the key's first letter in a palette colour.
 */
export function ReportImage({
  set,
  name,
  value,
  label,
  size = 40,
}: {
  set: ReportImageSet;
  name: unknown;
  /** A cached-URL set's own value for this row (the column the set declares). */
  value?: unknown;
  label?: string;
  size?: 20 | 40;
}) {
  const key = imageKey(name);
  const src = imageSrc(set, value) ?? (set.url && key ? `${set.url}${encodeURIComponent(key)}` : null);
  const [failed, setFailed] = useState<string | null>(null);
  const alt = label && label.trim() !== "" ? label : key;
  const box = { width: size, height: size };

  if (src && failed !== src) {
    return (
      <img
        src={src}
        alt={alt}
        loading="lazy"
        className="shrink-0 rounded-full object-cover"
        style={box}
        onError={() => setFailed(src)}
      />
    );
  }
  if ((set.fallback ?? "initial") === "none" || key === "") return null;
  return (
    <span
      role="img"
      aria-label={alt}
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${surfaceClass(roleFor(key))}`}
      style={{ ...box, fontSize: Math.round(size / 2.2) }}
    >
      {key.slice(0, 1).toUpperCase()}
    </span>
  );
}
