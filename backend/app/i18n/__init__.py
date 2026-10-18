"""Internationalization support for BizView."""

from __future__ import annotations

import contextvars
import logging
import threading
from contextlib import contextmanager
from typing import Any, Literal

logger = logging.getLogger(__name__)

Locale = Literal["es", "en"]
SUPPORTED: tuple[Locale, ...] = ("es", "en")

# Mutable box so a value set inside a sync dependency (threadpool, copied context)
# is visible to the exception handler of the same request.
class _Box:
    __slots__ = ("locale",)
    def __init__(self, locale: Locale) -> None:
        self.locale = locale

_context: contextvars.ContextVar[_Box | None] = contextvars.ContextVar(
    "i18n_locale_box", default=None
)

_missing_keys: set[str] = set()
_missing_lock = threading.Lock()


class _SafeDict(dict):
    """dict subclass that leaves missing placeholders as '{name}'."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def normalize(tag: str | None) -> Locale | None:
    """Return the primary subtag (lowercase) if supported, else None.

    >>> normalize('en-US')
    'en'
    >>> normalize('es_VE')
    'es'
    >>> normalize('fr')
    """
    if not tag:
        return None
    primary = tag.split("-")[0].split("_")[0].lower()
    if primary in SUPPORTED:
        return primary
    return None


def from_accept_language(header: str | None) -> Locale | None:
    """Parse an Accept-Language header and return the first supported locale.

    Handles q-values: sort by q descending, keep original order for ties, ignore q=0.
    """
    if not header:
        return None
    entries: list[tuple[str, float, int]] = []
    for idx, part in enumerate(header.split(",")):
        segment = part.strip()
        if not segment:
            continue
        pieces = segment.split(";")
        tag = pieces[0].strip()
        q = 1.0
        for param in pieces[1:]:
            param = param.strip()
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 0.0
        if q == 0.0:
            continue
        entries.append((tag, q, idx))
    # sort by q desc, then original order
    entries.sort(key=lambda x: (-x[1], x[2]))
    for tag, _q, _idx in entries:
        primary = normalize(tag)
        if primary:
            return primary
    return None


def open_box(locale: Locale) -> contextvars.Token[_Box | None]:
    """Set a NEW box in the current context and return its token for resetting."""
    box = _Box(locale)
    return _context.set(box)


def set_locale(locale: Locale) -> None:
    """Mutate the current box if one exists, otherwise open a new box."""
    box = _context.get()
    if box is not None:
        box.locale = locale
    else:
        open_box(locale)


def current() -> Locale:
    """Return the current locale from the context box, else from settings, else 'es'."""
    box = _context.get()
    if box is not None:
        return box.locale
    # Lazy import to avoid cycles.
    from app.config import get_settings
    settings = get_settings()
    return settings.default_locale if settings.default_locale in SUPPORTED else "es"


@contextmanager
def use_locale(locale: Locale):
    """Context manager that opens a new box and resets the contextvar on exit."""
    token = open_box(locale)
    try:
        yield
    finally:
        _context.reset(token)


def _get_catalogue(locale: Locale) -> dict[str, str]:
    """Dynamic import to avoid circular imports at module load."""
    if locale == "en":
        from . import en
        return en.MESSAGES
    from . import es
    return es.MESSAGES


def t(key: str, **params: Any) -> str:
    """Translate a key using the current locale, fallback to Spanish, then the key itself.

    Missing keys are logged only once (guarded by a lock).
    """
    locale = current()
    catalog = _get_catalogue(locale)
    text = catalog.get(key)
    if text is None:
        if locale != "es":
            es_catalog = _get_catalogue("es")
            text = es_catalog.get(key)
        if text is None:
            with _missing_lock:
                if key not in _missing_keys:
                    logger.warning("Missing i18n key: %s", key)
                    _missing_keys.add(key)
            return key
    return text.format_map(_SafeDict(params))


def tn(key: str, n: int, **params: Any) -> str:
    """Translate plural form: key.one for n==1, else key.other."""
    suffix = ".one" if n == 1 else ".other"
    params["n"] = n
    return t(f"{key}{suffix}", **params)


class M:
    """Lazy message: stores key and params, renders on demand."""
    __slots__ = ("key", "params")

    def __init__(self, key: str, **params: Any) -> None:
        self.key = key
        self.params = params

    def __str__(self) -> str:
        return t(self.key, **self.params)

    def __repr__(self) -> str:
        return f"M({self.key!r}, {self.params!r})"

    def to_json(self) -> dict[str, Any]:
        return {"key": self.key, "params": self.params}


def localized(obj: dict, field: str, locale: Locale | None = None) -> str | None:
    """Return the localized value from a dict.

    If locale is None, use the current locale.
    For 'en', prefer f'{field}_en' if it is a non-empty string, else the base field.
    For 'es', always use the base field.
    """
    if locale is None:
        locale = current()
    if locale == "en":
        en_val = obj.get(f"{field}_en")
        if isinstance(en_val, str) and en_val.strip():
            return en_val
    val = obj.get(field)
    if isinstance(val, str) and val.strip():
        return val
    return None


def to_stored(msg, redact=None) -> tuple[str | None, str | None, dict | None]:
    """(text, key, params) for a message written without a request (worker).

    The text is rendered in DEFAULT_LOCALE; params values that are `M` are stored
    as `{"$m": key, "params": {...}}` (recursively). Values already in that dict
    form are kept. `redact` (callable str->str) is applied to the rendered text
    and to every str param value. `None` -> (None, None, None); a plain `str` ->
    (redact(text), None, None).
    """
    from app.config import get_settings

    if msg is None:
        return None, None, None
    redact = redact or (lambda s: s)
    if isinstance(msg, str):
        return redact(msg), None, None

    def encode(value):
        if isinstance(value, M):
            return {
                "$m": value.key,
                "params": {k: encode(v) for k, v in value.params.items()},
            }
        if isinstance(value, dict) and "$m" in value:
            return value
        if isinstance(value, str):
            return redact(value)
        return value

    params = {k: encode(v) for k, v in msg.params.items()}
    with use_locale(get_settings().default_locale):
        text = str(msg)
    return redact(text), msg.key, params


def render_stored(text, key, params) -> str | None:
    """The stored message in the current language.

    Legacy rows (no key) and unknown keys return `text` as recorded. Nested
    `{"$m": ...}` params are rebuilt into `M` objects before calling
    `t(key, **params)`. If `t` returns the key itself (missing id), return
    `text`.
    """
    if not key:
        return text

    def decode(value):
        if isinstance(value, dict) and "$m" in value:
            return M(value["$m"], **decode(value.get("params") or {}))
        if isinstance(value, dict):
            return {k: decode(v) for k, v in value.items()}
        if isinstance(value, list):
            return [decode(v) for v in value]
        return value

    rendered = t(key, **decode(params or {}))
    return text if rendered == key else rendered


# The CLI validator and SQL checks run inside the backend: their messages follow the same
# language as the request or job (feature 022, T039).
from bizview_cli import i18n as _cli_i18n  # noqa: E402

_cli_i18n.set_resolver(current)
