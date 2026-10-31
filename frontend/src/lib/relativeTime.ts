import { t } from "../i18n/live";
import { dateTimeFormat } from "./intl";

/** "now", "12 min", "3 h", "5 d", or a short date: how a project shortcut reads a timestamp. */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const date = new Date(iso).getTime();
  const minutes = Math.floor(Math.max(0, now - date) / 60_000);
  if (minutes < 1) return t.common.justNow;
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} d`;
  return dateTimeFormat({ day: "numeric", month: "short" }).format(new Date(date));
}
