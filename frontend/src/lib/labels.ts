/** Optional English texts authored in report.yaml (`<field>_en`, feature 022 FR-009). */
import { currentLocale } from "../i18n/live";
import type { Locale } from "../i18n/resolve";

export function localized<T extends object, K extends keyof T & string>(
  obj: T,
  field: K,
  locale?: Locale,
): T[K];
export function localized<T extends object, K extends keyof T & string>(
  obj: T | null | undefined,
  field: K,
  locale?: Locale,
): T[K] | undefined;
export function localized<T extends object, K extends keyof T & string>(
  obj: T | null | undefined,
  field: K,
  locale?: Locale,
): T[K] | undefined {
  if (obj == null) return undefined;
  const lang = locale ?? currentLocale();
  if (lang === "en") {
    const english = (obj as Record<string, unknown>)[`${field}_en`];
    if (typeof english === "string" && english.trim() !== "") {
      return english as T[K];
    }
  }
  return obj[field];
}
