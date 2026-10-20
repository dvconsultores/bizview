import type { CommandSuggestionItem } from "../../api/types";
import { useT } from "../../i18n";

const MAX_SUGGESTIONS = 3;

/** Backticked `/name args` snippets of an assistant reply whose name is a registry command. */
export function inlineSuggestions(content: string, names: string[]): CommandSuggestionItem[] {
  const known = new Set(names);
  const seen = new Set<string>();
  const out: CommandSuggestionItem[] = [];
  for (const match of content.matchAll(/`\/([^`\n]+)`/g)) {
    const [command, ...rest] = match[1].trim().split(/\s+/);
    if (!known.has(command)) continue;
    const args = rest.join(" ");
    const key = `${command} ${args}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ command, arguments: args });
    if (out.length === MAX_SUGGESTIONS) break;
  }
  return out;
}

/** "Insertar `/speckit-…`" buttons: they fill the composer, never send (feature 021 FR-005). */
export function CommandSuggestions(props: {
  items: CommandSuggestionItem[];
  onInsert: (text: string) => void;
}) {
  const t = useT();
  if (props.items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {props.items.map((item) => {
        const parts = [`/${item.command}`];
        if (item.spec && !item.arguments.includes(item.spec)) parts.push(item.spec);
        if (item.arguments) parts.push(item.arguments);
        const text = parts.join(" ").trim();
        return (
          <button
            key={text}
            type="button"
            data-command-suggestion=""
            onClick={() => props.onInsert(`${text} `)}
            aria-label={t.assistant.commands.insertLabel.replace("{command}", text)}
            className="inline-flex min-h-tap min-w-0 max-w-full items-center gap-2 rounded-full border border-accent-line bg-accent-soft px-3 text-sm text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <span className="shrink-0">{t.assistant.commands.insert}</span>
            <code className="min-w-0 truncate font-mono" title={text}>{text}</code>
          </button>
        );
      })}
    </div>
  );
}
