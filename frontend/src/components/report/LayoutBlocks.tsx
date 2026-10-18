import { Fragment, useMemo, type ReactNode } from "react";
import type { ReportData, ReportDefinition, WebComponent } from "../../api/types";
import { localized } from "../../lib/labels";
import type { ReportSelection } from "../../lib/reportQuery";
import { useT } from "../../i18n";
import { Card } from "../Card";
import { ParamsForm, type ParamsFormProps } from "./ParamsForm";
import { fontClass } from "./layoutRoles";

/** Feature 026: the layout's `text`, `filters` and `spacer` components. No component here reads a
 * URL, an HTML string or a colour literal from the layout, and nothing is `eval`ed. */

/** The report's own filter controls need the wiring the report screen already owns (applied
 * selection, the apply callback and the option loader); `ReportViews` passes it through. */
export interface LayoutParamsWiring {
  applied: ReportSelection;
  onApply: (selection: ReportSelection) => void;
  loadOptions: ParamsFormProps["loadOptions"];
}

const SAFE_HREF = /^(https?:\/\/|\/|#|mailto:)/i;
const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)\s]+\))/g;

function safeHref(href: string): string | null {
  const value = href.trim();
  return SAFE_HREF.test(value) ? value : null;
}

function inlineNodes(line: string, lineIndex: number): ReactNode[] {
  return line.split(INLINE).map((token, tokenIndex) => {
    const key = `${lineIndex}-${tokenIndex}`;
    if (/^\*\*[^*]+\*\*$/.test(token)) return <strong key={key}>{token.slice(2, -2)}</strong>;
    if (/^\*[^*]+\*$/.test(token) || /^_[^_]+_$/.test(token)) return <em key={key}>{token.slice(1, -1)}</em>;
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(token);
    if (link) {
      const href = safeHref(link[2]);
      if (!href) return <Fragment key={key}>{link[1]}</Fragment>;
      const external = /^https?:/i.test(href);
      return (
        <a
          key={key}
          href={href}
          className="text-accent underline underline-offset-2"
          {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        >
          {link[1]}
        </a>
      );
    }
    return <Fragment key={key}>{token}</Fragment>;
  });
}

/** The markdown subset a `text` block allows: bold, italics, links and line breaks. Rendered as
 * React elements, never as HTML. */
export function markdownNodes(text: string): ReactNode[] {
  return text.split("\n").flatMap((line, index) =>
    index === 0 ? inlineNodes(line, index) : [<br key={`br-${index}`} />, ...inlineNodes(line, index)],
  );
}

export function TextBlock({ component }: { component: WebComponent }) {
  const text = localized(component, "text") ?? "";
  const font = fontClass(component.font_name);
  const style = component.style ?? "paragraph";

  if (style === "heading") {
    return (
      <h2 className={`text-lg font-semibold text-ink [overflow-wrap:anywhere] ${font}`}>
        {markdownNodes(text)}
      </h2>
    );
  }
  if (style === "caption") {
    return <p className={`text-xs text-ink-muted [overflow-wrap:anywhere] ${font}`}>{markdownNodes(text)}</p>;
  }
  return <p className={`text-sm leading-relaxed text-ink-2 [overflow-wrap:anywhere] ${font}`}>{markdownNodes(text)}</p>;
}

/** `only[]` restricts which of the report's filters appear; the ids are validated by the CLI. */
function filterIds(component: WebComponent, def: ReportDefinition): string[] {
  const declared = def.filters ?? [];
  if (!component.only || component.only.length === 0) return declared;
  const wanted = new Set(component.only);
  return declared.filter((id) => wanted.has(id));
}

export function FiltersBlock({
  component,
  def,
  data,
  params,
}: {
  component: WebComponent;
  def: ReportDefinition;
  data: ReportData;
  params?: LayoutParamsWiring;
}) {
  const t = useT();
  const ids = useMemo(() => filterIds(component, def), [component, def]);
  const restricted = useMemo<ReportDefinition>(() => ({ ...def, filters: ids }), [def, ids]);

  if (params) {
    return (
      <Card className="p-5 sm:p-6">
        <ParamsForm
          def={restricted}
          applied={params.applied}
          onApply={params.onApply}
          loadOptions={params.loadOptions}
        />
      </Card>
    );
  }

  // No wiring (the assistant preview and the shared dashboard own no filter state): the applied
  // filters are shown as they came with the payload instead of a control that could not apply.
  const applied = ids
    .map((id) => ({ id, label: localized(def.dimensions[id], "label") ?? id, values: data.filters[id] ?? [] }))
    .filter((entry) => entry.values.length > 0);

  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{t.reportParams.filtersSection}</h2>
      {applied.length === 0 ? (
        <p className="mt-2 text-sm text-ink-muted">{t.layout.filtersNone}</p>
      ) : (
        <ul className="mt-3 space-y-1.5 text-sm">
          {applied.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-ink-soft">{entry.label}</span>
              <span className="min-w-0 [overflow-wrap:anywhere] text-ink-2">{entry.values.join(", ")}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** An empty cell: the declared step from the desktop breakpoint, the small one on phones. */
const SPACER: Record<string, string> = {
  sm: "h-3",
  md: "h-3 md:h-6",
  lg: "h-3 md:h-10",
};

export function SpacerBlock({ component }: { component: WebComponent }) {
  return <div className={SPACER[component.size ?? "md"] ?? SPACER.md} aria-hidden />;
}
