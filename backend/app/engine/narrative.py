"""AI narrative of a report (feature 005, research R6, FR-003).

The ONLY product code path that sends data to the AI provider. What is sent: the report title,
the period dates, the labels and aggregated values of the metrics the report spec lists in
`ai_narrative.inputs` (current and, when declared, comparison period), the LABELS of active
filters (never their values: a dimension may hold names of people or customers), and the spec's
instructions. Never rows, never other metrics, never user data.
"""
from app.ai import get_provider
from app.config import Settings
from app.engine import periods
from app.engine.report import Context, aggregate
from app.i18n import t

SYSTEM = ("Eres un analista de negocio. Escribes en español, breve y concreto, sin inventar "
          "cifras: usa solo los valores entregados. Si un valor falta, dilo.")


def system() -> str:
    """System prompt in the request language (feature 022); SYSTEM is its Spanish source."""
    return t("narrative.system")


def _fmt(v: float | None) -> str:
    if v is None:
        return t("narrative.no_value")
    return f"{v:,.2f}"


def inputs(ctx: Context, sel: periods.Selection, filters: dict, tz: str) -> dict:
    ai = ctx.definition.get("ai_narrative") or {}
    metric_ids = list(ai.get("inputs") or [])
    cur = aggregate(ctx, metric_ids, sel.current, filters, tz)[0]
    with_prev = bool(ai.get("with_comparison", True)) and sel.previous is not None
    prev = aggregate(ctx, metric_ids, sel.previous, filters, tz)[0] if with_prev else {}
    return {"metrics": [{"id": m, "label": ctx.metrics[m]["label"], "value": cur.get(m),
                         "previous": prev.get(m) if with_prev else None}
                        for m in metric_ids],
            "with_comparison": with_prev}


def build_prompt(ctx: Context, sel: periods.Selection, filters: dict, data: dict) -> str:
    ai = ctx.definition.get("ai_narrative") or {}
    lines = [t("narrative.report", title=ctx.definition['title']),
             t("narrative.period", start=sel.current.start.isoformat(),
               end=sel.current.end.isoformat())
             + (t("narrative.in_progress") if sel.partial else "")]
    if data["with_comparison"]:
        lines.append(t("narrative.compare", start=sel.previous.start.isoformat(),
                       end=sel.previous.end.isoformat()))
    if filters:
        parts = []
        for d in sorted(filters):
            label = ctx.dimensions[d]["label"]
            count = len(filters[d]) if isinstance(filters[d], list) else 1
            parts.append(t("narrative.selected_one" if count == 1 else "narrative.selected_many",
                           label=label, n=count))
        lines.append(t("narrative.filtered_by", filters=", ".join(parts)))
    lines.append(t("narrative.figures"))
    for m in data["metrics"]:
        row = f"- {m['label']}: {_fmt(m['value'])}"
        if data["with_comparison"]:
            row += t("narrative.previous", value=_fmt(m['previous']))
        lines.append(row)
    lines.append("")
    lines.append(ai.get("instructions") or t("narrative.default_instruction"))
    return "\n".join(lines)


def generate(ctx: Context, sel: periods.Selection, filters: dict, tz: str,
             settings: Settings) -> str:
    provider = get_provider(settings)            # AIError('not_configured') when AI is off
    prompt = build_prompt(ctx, sel, filters, inputs(ctx, sel, filters, tz))
    reply = provider.complete(prompt, system=system(), max_tokens=800, effort="low")
    return reply.text.strip()
