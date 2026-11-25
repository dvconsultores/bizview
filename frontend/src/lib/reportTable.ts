import type { ReportData, ReportDefinition } from "../api/types";
import { componentView } from "../components/report/LayoutRenderer";
import { VIEW_CARD_PREFIX } from "../components/report/ReportViews";
import { cardTitle } from "./cardTitle";
import { localized } from "./labels";

/**
 * Feature 064: the view, component and title behind a `?tabla=` id.
 *
 * Shared by the signed-in report page, the public share link (018) and the widget (065), so all
 * three open the same table for the same card. Copy/CSV decisions stay with the caller.
 */
export function tableEntry(id: string, data: ReportData, report: ReportDefinition) {
  if (report.interactions?.data_table === false) return null;
  if (id.startsWith(VIEW_CARD_PREFIX)) {
    const view = data.views[Number(id.slice(VIEW_CARD_PREFIX.length))];
    if (!view || view.error || view.empty) return null;
    const title = ("title" in view && localized(view as { title?: string }, "title"))
      || (view.type === "ranking" ? localized(view, "label") : undefined)
      || localized(report, "title");
    return { view, title };
  }
  const component = (report.layout?.web?.components ?? []).find((entry) => entry.id === id);
  if (!component || component.data_table === false) return null;
  const base = component.view ? data.views.find((view) => view.id === component.view) : undefined;
  if (!base || base.error || base.empty) return null;
  return {
    view: componentView(component, base, data),
    component,
    title: cardTitle(report, id, base as { title?: string }) ?? localized(report, "title"),
  };
}
