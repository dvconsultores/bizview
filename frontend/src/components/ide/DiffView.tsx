import type { DiffHunk } from "../../api/types";
import { useT } from "../../i18n";

interface Row { old: number | null; next: number | null; t: " " | "+" | "-"; text: string; gap?: boolean }

function rows(hunks: DiffHunk[]): Row[] {
  const out: Row[] = [];
  hunks.forEach((hunk, index) => {
    if (index > 0) out.push({ old: null, next: null, t: " ", text: "", gap: true });
    let old = hunk.a_start;
    let next = hunk.b_start;
    for (const line of hunk.lines) {
      out.push({ old: line.t === "+" ? null : old, next: line.t === "-" ? null : next, t: line.t,
                 text: line.text });
      if (line.t !== "+") old += 1;
      if (line.t !== "-") next += 1;
    }
  });
  return out;
}

/** Line diff table (old/new line numbers); wraps long lines so it fits 375 px. */
export function DiffView(props: { hunks: DiffHunk[]; truncated: boolean; caption: string }) {
  const t = useT();
  if (props.hunks.length === 0) return <p className="p-3 text-sm text-ink-muted">{t.projects.noDiff}</p>;
  return (
    <div>
      <table className="w-full table-fixed border-collapse">
        <caption className="sr-only">{props.caption}</caption>
        <colgroup>
          <col className="w-10" />
          <col className="w-10" />
          <col className="w-6" />
          <col />
        </colgroup>
        <tbody>
          {rows(props.hunks).map((row, i) =>
            row.gap ? (
              <tr key={i} aria-hidden><td colSpan={4} className="h-3 border-y border-line bg-subtle" /></tr>
            ) : (
              <tr key={i} className={row.t === "+" ? "bg-success-soft" : row.t === "-" ? "bg-danger-soft" : ""}>
                <td className="select-none px-1 text-right align-top font-mono text-xs text-ink-soft">{row.old ?? ""}</td>
                <td className="select-none px-1 text-right align-top font-mono text-xs text-ink-soft">{row.next ?? ""}</td>
                <td className={`select-none text-center align-top font-mono text-xs ${row.t === "+" ? "text-success" : "text-danger"}`}>
                  {row.t !== " " && <span aria-hidden>{row.t}</span>}
                  {row.t !== " " && <span className="sr-only">{row.t === "+" ? t.projects.added : t.projects.removed}</span>}
                </td>
                <td className="whitespace-pre-wrap break-all px-2 py-0.5 font-mono text-xs text-ink">{row.text}</td>
              </tr>
            ),
          )}
        </tbody>
      </table>
      {props.truncated && <p className="border-t border-line px-3 py-2 text-xs text-ink-muted">{t.projects.diffTruncated}</p>}
    </div>
  );
}
