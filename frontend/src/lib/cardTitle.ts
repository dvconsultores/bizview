import type { ReportDefinition, WebComponent } from "../api/types";
import { localized } from "./labels";

/**
 * Feature 062: the words a maximized card is titled with, and the words its **Ampliar** button
 * announces.
 *
 * 056 fell back to `Ampliar «k_ventas»` — the component's id, which is a handle written in
 * `report.yaml` and means nothing to a reader. The order below only ever produces text a reader can
 * see on the card:
 *
 * 1. the component's own `title` (localised);
 * 2. the title of the view it draws (a view always has one);
 * 3. for a `kpi`, the label of the metric it shows;
 * 4. for a `text`, its first words;
 * 5. the report's own title.
 *
 * The id is the one thing this function never returns.
 */
export function cardTitle(def: ReportDefinition, id: string,
                          view?: { title?: string }): string | undefined {
  const components = (def.layout?.web?.components ?? []) as WebComponent[];
  const component = components.find((entry) => entry.id === id);
  const metric = component?.metric ? def.metrics[component.metric] : undefined;
  const candidates = [
    component ? localized(component, "title") : undefined,
    view?.title,
    metric ? localized(metric, "label") : undefined,
    component?.type === "text" ? textWords(component) : undefined,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim() !== "") return candidate.trim();
  }
  return def.title?.trim() || undefined;
}

/** The first words of a `text` component, on one line: enough to recognise the paragraph. */
export function textWords(component: WebComponent | undefined, words = 8): string | undefined {
  const raw = (component as { text?: unknown } | undefined)?.text;
  const text = typeof raw === "string" ? raw : "";
  const flat = text.replace(/\s+/g, " ").trim();
  return flat ? flat.split(" ").slice(0, words).join(" ") : undefined;
}
