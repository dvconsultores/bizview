import { ApiError } from "../api/client";
import type { ReportSelection } from "./reportQuery";
import type { SubscriptionFrequency } from "../api/types";
import { t } from "../i18n/live";

export const LINK_DAY_CHIPS = [1, 7, 30, 90] as const;

export function selectionPayload(
  s: ReportSelection,
): Record<string, string | string[]> {
  const payload: Record<string, string | string[]> = {
    period: s.period,
    compare: s.compare,
  };
  if (s.period === "custom") {
    if (s.from) payload.from = s.from;
    if (s.to) payload.to = s.to;
  }
  for (const [id, values] of Object.entries(s.filters)) {
    if (values.length > 0) payload[`filter.${id}`] = values;
  }
  return payload;
}

export function isValidEmail(value: string): boolean {
  const email = value.trim();
  const parts = email.split("@");
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  if (!local || local.includes(" ")) return false;
  if (!domain.includes(".")) return false;
  const labels = domain.split(".");
  if (labels.some((label) => !/^[a-z0-9-]+$/i.test(label) || !label)) {
    return false;
  }
  const tld = labels[labels.length - 1];
  return /^[a-z]{2,}$/i.test(tld);
}

export function emailDomain(value: string): string {
  const idx = value.lastIndexOf("@");
  return idx >= 0 ? value.slice(idx + 1).toLowerCase() : "";
}

export function domainAllowed(value: string, domains: string[]): boolean {
  const domain = emailDomain(value);
  return domains.some((d) => d.toLowerCase() === domain);
}

export function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

export function scheduleText(s: {
  frequency: SubscriptionFrequency;
  hour: number;
  weekday: number | null;
  monthday: number | null;
}): string {
  const time = hourLabel(s.hour);
  switch (s.frequency) {
    case "daily":
      return t.sharing.schedules.everyDay(time);
    case "weekly":
      return t.sharing.schedules.everyWeek(t.sharing.schedules.weekdays[s.weekday ?? 0], time);
    case "monthly":
      return t.sharing.schedules.everyMonth(s.monthday ?? 1, time);
  }
}

export function errorText(e: unknown): string {
  return e instanceof ApiError ? e.message : t.common.unexpected;
}
