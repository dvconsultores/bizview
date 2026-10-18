export type Locale = "es" | "en";

export type LocalePreference = Locale | null;

export const LOCALE_STORAGE_KEY = "bizview.locale";

export function normalizeLocale(tag?: string | null): Locale | null {
  if (!tag) return null;
  const primary = tag.trim().toLowerCase().split(/[-_]/)[0];
  return primary === "es" || primary === "en" ? primary : null;
}

export function browserLocale(languages: readonly string[]): Locale | null {
  for (const lang of languages) {
    const locale = normalizeLocale(lang);
    if (locale) return locale;
  }
  return null;
}

export function resolveLocale(input: {
  account?: LocalePreference;
  device?: string | null;
  languages?: readonly string[];
  defaultLocale?: string | null;
}): Locale {
  if (input.account) return input.account;
  const deviceLocale = normalizeLocale(input.device);
  if (deviceLocale) return deviceLocale;
  const browser = input.languages ? browserLocale(input.languages) : null;
  if (browser) return browser;
  const defaultLocale = normalizeLocale(input.defaultLocale);
  if (defaultLocale) return defaultLocale;
  return "es";
}

export function intlTag(locale: Locale): string {
  return locale === "es" ? "es-ES" : "en-US";
}
