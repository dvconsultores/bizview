import { currentIntlTag } from "../i18n/live";

const numberFormatters = new Map<string, Intl.NumberFormat>();
const dateTimeFormatters = new Map<string, Intl.DateTimeFormat>();

/** Intl constructors are costly; one instance per language + options. */
export function numberFormat(options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = `${currentIntlTag()}|${JSON.stringify(options)}`;
  let formatter = numberFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(currentIntlTag(), options);
    numberFormatters.set(key, formatter);
  }
  return formatter;
}

/** Same cache for dates; a constructor that throws (unknown time zone) stores nothing. */
export function dateTimeFormat(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${currentIntlTag()}|${JSON.stringify(options)}`;
  let formatter = dateTimeFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(currentIntlTag(), options);
    dateTimeFormatters.set(key, formatter);
  }
  return formatter;
}
