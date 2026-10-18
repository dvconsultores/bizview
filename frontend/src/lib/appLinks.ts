import { canOpen, matchRoute, type Viewer } from "./routeAccess";

/** Pieces of a chat answer: plain text, or an in-app link `[label](app:/path)` (feature 023).
 * Only the `app:` scheme becomes a link; any other `[x](…)` stays literal text. */
export type AppLinkPart = { text: string; to?: string };

const LINK = /\[([^\][\n]+)\]\(app:(\/[^)\s]*)\)/g;

export function splitAppLinks(text: string): AppLinkPart[] {
  const parts: AppLinkPart[] = [];
  let last = 0;
  for (const match of text.matchAll(LINK)) {
    const index = match.index ?? 0;
    if (index > last) parts.push({ text: text.slice(last, index) });
    parts.push({ text: match[1], to: match[2] });
    last = index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}

/** The path when it is a real route the viewer can open, else null (shown as plain text). */
export function resolveAppLink(to: string, user: Viewer | null): string | null {
  if (!to.startsWith("/") || matchRoute(to) === null) return null;
  return canOpen(to, user) ? to : null;
}
