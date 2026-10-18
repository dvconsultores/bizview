import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { CommandDef } from "../../api/types";
import { useLocale } from "../../i18n";

/** The chat's `/` commands (feature 021), fetched once per language. */
const cache = new Map<string, Promise<CommandDef[]>>();

export function __resetCommandsCache() {
  cache.clear();
}

/** Loads on first need (`enabled`: the user typed `/` or a reply names a command). */
export function useCommands(enabled = true): CommandDef[] | null {
  const { locale } = useLocale();
  const [commands, setCommands] = useState<CommandDef[] | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let promise = cache.get(locale);
    if (!promise) {
      promise = api
        .get<{ items: CommandDef[] }>("/api/assistant/commands")
        .then((res) => res.items)
        .catch(() => {
          cache.delete(locale);
          return [] as CommandDef[];
        });
      cache.set(locale, promise);
    }
    void promise.then((items) => {
      if (!cancelled) setCommands(items);
    });
    return () => {
      cancelled = true;
    };
  }, [locale, enabled]);

  return commands;
}
