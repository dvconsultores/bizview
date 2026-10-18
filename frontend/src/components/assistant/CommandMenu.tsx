import { useEffect } from "react";
import type { CommandDef } from "../../api/types";
import { useT } from "../../i18n";

/** Prefix matches first (with or without `speckit-`), then name/description substrings. */
export function filterCommands(commands: CommandDef[], query: string): CommandDef[] {
  const q = query.toLowerCase().trim();
  if (!q) return commands;
  const prefix: CommandDef[] = [];
  const contains: CommandDef[] = [];
  for (const cmd of commands) {
    const name = cmd.name.toLowerCase();
    if (name.startsWith(q) || name.replace(/^speckit-/, "").startsWith(q)) prefix.push(cmd);
    else if (name.includes(q) || cmd.description.toLowerCase().includes(q)) contains.push(cmd);
  }
  return [...prefix, ...contains];
}

/** The menu's query while the caret is inside the first token of a `/…` message, else null. */
export function menuQuery(text: string, caret: number): string | null {
  if (caret < 1 || !text.startsWith("/")) return null;
  const token = text.slice(0, caret);
  return /\s/.test(token) ? null : token.slice(1);
}

/** Inline listbox under the composer (feature 021 plan §10); the textarea is its combobox. */
export function CommandMenu(props: {
  id: string;
  items: CommandDef[];
  activeIndex: number;
  hasSpec: boolean;
  optionId: (index: number) => string;
  onSelect: (cmd: CommandDef) => void;
  onActiveChange: (index: number) => void;
}) {
  const t = useT();
  const { id, items, activeIndex, hasSpec, optionId, onSelect, onActiveChange } = props;

  useEffect(() => {
    if (items.length === 0) return;
    const el = document.getElementById(optionId(activeIndex));
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  }, [activeIndex, items.length, optionId]);

  return (
    <div
      data-command-menu=""
      className="max-h-[min(50vh,20rem)] overflow-y-auto rounded-xl border border-line bg-surface shadow-raised"
    >
      <ul role="listbox" id={id} aria-label={t.assistant.commands.menuLabel}>
        {items.length === 0 ? (
          <li role="presentation" className="px-3 py-2 text-sm text-ink-muted">
            {t.assistant.commands.noMatches}
          </li>
        ) : (
          items.map((cmd, i) => (
            <li
              key={cmd.name}
              role="option"
              id={optionId(i)}
              aria-selected={i === activeIndex}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => onSelect(cmd)}
              onPointerEnter={() => onActiveChange(i)}
              className={`flex min-h-tap cursor-pointer flex-col justify-center px-3 py-2 ${
                i === activeIndex ? "bg-subtle" : ""
              }`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm text-ink">/{cmd.name}</span>
                {cmd.needs_spec && !hasSpec ? (
                  <span className="rounded-full bg-warning-soft px-2 text-xs text-warning-strong">
                    {t.assistant.commands.needsSpec}
                  </span>
                ) : null}
              </span>
              <span className="line-clamp-2 text-sm text-ink-muted">{cmd.description}</span>
            </li>
          ))
        )}
      </ul>
      <p className="sr-only" aria-live="polite">
        {items.length === 0
          ? t.assistant.commands.noMatches
          : t.assistant.commands.count(items.length)}
      </p>
    </div>
  );
}
