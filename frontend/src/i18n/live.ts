/* Feature 022: live ES-module binding of the active catalogue (plan D2).
 * Non-component code (api client, lib/*) reads it at call time, so it follows
 * the language without a hook. Kept free of React and the API client to
 * avoid an import cycle. */
import { en } from "./en";
import { es, type Catalogue } from "./es";
import { intlTag, type Locale } from "./resolve";

export const CATALOGUES: Record<Locale, Catalogue> = { es, en };

export let t: Catalogue = es;
let active: Locale = "es";

/** Called by LocaleProvider during render and by unit tests. */
export function activate(locale: Locale) {
  active = locale;
  t = CATALOGUES[locale];
}

export function currentLocale(): Locale {
  return active;
}

export function currentIntlTag(): string {
  return intlTag(active);
}
