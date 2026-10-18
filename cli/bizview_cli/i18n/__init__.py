"""CLI messages in Spanish or English (feature 022, plan D10)."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

Lang = Literal["es", "en"]
LANGS = ("es", "en")
DEFAULT: Lang = "es"

_lang: ContextVar[Lang | None] = ContextVar("bizview_cli_lang", default=None)
_resolver: Callable[[], str | None] | None = None


class _Safe(dict):
    """Mapping that renders missing format keys as ``{key}``."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def normalize(tag: str | None) -> Lang | None:
    """Return the primary language subtag when it is supported, else ``None``."""

    if not tag:
        return None
    value = re.split(r"[-_.@]", tag.strip().lower(), maxsplit=1)[0]
    return value if value in LANGS else None


def set_resolver(fn: Callable[[], str | None] | None) -> None:
    """Set or clear the embedding application's language resolver."""

    global _resolver
    _resolver = fn


@contextmanager
def use_lang(lang: str | None):
    """Temporarily override the CLI language."""

    token = _lang.set(normalize(lang))
    try:
        yield
    finally:
        _lang.reset(token)


def current() -> Lang:
    """Resolve the active language from the most specific source available."""

    ctx = _lang.get()
    if ctx is not None:
        return ctx

    if _resolver is not None:
        try:
            resolved = normalize(_resolver())
        except Exception:
            resolved = None
        if resolved is not None:
            return resolved

    env_lang = normalize(os.environ.get("BIZVIEW_LANG"))
    if env_lang is not None:
        return env_lang

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            normalized = normalize(value)
            return normalized if normalized is not None else DEFAULT

    return DEFAULT


def _catalogue(lang: Lang) -> dict[str, str]:
    """Import and return the catalogue for *lang* lazily."""

    if lang == "en":
        from . import en

        return en.MESSAGES
    from . import es

    return es.MESSAGES


def t(key: str, /, **params) -> str:
    """Return the translated template for *key*, optionally interpolating *params*."""

    messages = _catalogue(current())
    template = messages.get(key)
    if template is None:
        template = _catalogue("es").get(key, key)
    if not params:
        return template
    return template.format_map(_Safe(params))
