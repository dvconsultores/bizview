"""Typed report-render errors (feature 038).

A report can fail *after* its spec validated: the preview schemas were dropped, a dataset table
is gone, a join cannot be built, a metric divides by zero, a block cannot be drawn. Every one of
those used to end in the generic 500 («Ocurrió un error inesperado») that names nothing, so
nothing could be done about it.

Each failure now has a code the screen knows how to explain (es/en) and the ids that failed —
dataset, sets and key, metric, component, block. **Never a row value**: the detail is built from
identifiers and fixed reason tokens, so a code cannot leak data (constitution VIII).
"""

from __future__ import annotations

from typing import Any

from app.errors import ApiError

PREVIEW_EXPIRED = "preview_expired"
DATASET_MISSING = "dataset_missing"
JOIN_FAILED = "join_failed"
EMPTY_DATASET = "empty_dataset"
METRIC_ERROR = "metric_error"
LAYOUT_COMPONENT_UNKNOWN = "layout_component_unknown"
FORMAT_UNKNOWN = "format_unknown"
PDF_RENDER = "pdf_render"

CODES: tuple[str, ...] = (
    PREVIEW_EXPIRED,
    DATASET_MISSING,
    JOIN_FAILED,
    EMPTY_DATASET,
    METRIC_ERROR,
    LAYOUT_COMPONENT_UNKNOWN,
    FORMAT_UNKNOWN,
    PDF_RENDER,
)

#: The `format` values the payload renderers know. Anything else is a typed error, never a
#: number formatted as if it were something else.
FORMATS: tuple[str, ...] = ("number", "integer", "currency", "percent", "text")


def _clean(detail: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in detail.items() if v is not None and v != ""}


class RenderError(ApiError):
    """A render failure that names its code and the piece that failed."""

    def __init__(self, code: str, message: str, *, status: int = 422,
                 report_id: str | None = None, reference: str | None = None,
                 **detail: Any) -> None:
        self.detail = _clean(detail)
        extra = {"code": code,
                 **({"report": report_id} if report_id else {}),
                 **({"reference": reference} if reference else {}),
                 **self.detail}
        super().__init__(status, code, message, extra=extra)


def card(code: str, message: str, *, report_id: str | None = None,
         reference: str | None = None, **detail: Any) -> dict:
    """The `error` object a view (or PDF block) carries: one tile fails, the rest still renders."""
    return {"code": code, "message": message,
            **({"report": report_id} if report_id else {}),
            **({"reference": reference} if reference else {}),
            **_clean(detail)}



def check_format(value: Any, *, metric: str | None = None, report_id: str | None = None) -> str:
    """The declared `format`, or `format_unknown` naming the metric it belongs to."""
    fmt = value if isinstance(value, str) and value else "number"
    if fmt in FORMATS:
        return fmt
    from app.i18n import M

    raise RenderError(
        FORMAT_UNKNOWN, str(M("render.format_unknown", format=fmt, metric=metric or "?")),
        status=409, report_id=report_id, metric=metric, format=fmt,
    )
