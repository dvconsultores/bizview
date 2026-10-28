"""Deterministic corrections as JSON Pointer operations on a YAML document (feature 035).

A validation problem that is fully understood publishes `fix_data` — `{file, json_path, op,
value}` — next to the human `Arreglo:` text. The product applies it without an AI: load the YAML,
walk the pointer, do one of three operations, dump it back. The same functions run in the CLI tests
and in the backend endpoint, so a fix that validates is a fix that applies.

`op` values:

- `set`    — replace (or create) the value at the pointer.
- `append` — append to the array at the pointer, creating it when missing.
- `insert` — insert into the array at the pointer; `value` is `{"index": n, "value": …}`.
- `remove` — delete the array item (or the key) at the pointer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

OPS = ("set", "append", "insert", "remove")

# A fix may only change *content*. Task status (`- [ ]`/`- [X]`) and the spec's `**Status**:`
# line are evidence of work done, so no fix — and no fix message — may touch them (feature 040,
# FR-004: the 039 validator offered «marca todas las tareas como - [X]», which faked the result).
FORBIDDEN_FIX_PATHS = re.compile(r"^/(?:status|tasks?)(?:/|\b)", re.I)
FORBIDDEN_FIX_TEXT = re.compile(r"\[\s*[xX ]\s*\]|\*\*status\*\*\s*:|mark (?:every|all) task",
                                 re.I)


@dataclass(frozen=True)
class DeterministicFix:
    """One registered deterministic correction: the problem code and the content it changes."""

    code: str
    content: str


DETERMINISTIC_FIXES: tuple[DeterministicFix, ...] = (
    DeterministicFix("unjoined_sets", "the report's joins"),
    DeterministicFix("schedule_missing", "the integration's schedule"),
    DeterministicFix("label_missing", "a metric or dimension label"),
    DeterministicFix("view_type_unknown", "a view's type"),
    DeterministicFix("invalid_reference", "a date reference"),
    DeterministicFix("layout_palette_missing", "the installation's palette"),
    DeterministicFix("layout_filter_missing", "a filter's column"),
    DeterministicFix("timestamp_unit_mismatch", "a mapped time field's timestamp_unit"),
)


def is_content_fix(fix: dict) -> bool:
    """Whether a `fix_data` payload changes content and only content (040, FR-004)."""
    if not isinstance(fix, dict):
        return False
    if fix.get("op") not in OPS:
        return False
    if FORBIDDEN_FIX_PATHS.match(str(fix.get("json_path") or "")):
        return False
    return not FORBIDDEN_FIX_TEXT.search(str(fix.get("value") or ""))


class FixError(ValueError):
    """The operation cannot be applied here: the file moved on, or the path is wrong."""


def pointer_parts(json_path: str) -> list[str]:
    """Split a JSON Pointer into keys (`~1` and `~0` unescaped, as RFC 6901 says)."""
    if not isinstance(json_path, str) or not json_path.startswith("/"):
        raise FixError(f"json_path must start with '/': {json_path!r}")
    return [part.replace("~1", "/").replace("~0", "~")
            for part in json_path.split("/")[1:]]


def _index(node: Any, key: str) -> int:
    try:
        return int(key)
    except (TypeError, ValueError):
        raise FixError(f"not an array index: {key!r}") from None


def _walk(doc: Any, parts: list[str]) -> tuple[Any, str]:
    """The container that holds the last key, plus that key."""
    node = doc
    for part in parts[:-1]:
        if isinstance(node, list):
            node = node[_index(node, part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise FixError(f"path does not exist: /{'/'.join(parts[:-1])}")
    return node, parts[-1]


def apply_fix(doc: Any, json_path: str, op: str, value: Any) -> Any:
    """Apply one operation to `doc` in place and return it (dict/list documents only)."""
    if op not in OPS:
        raise FixError(f"unknown op: {op!r}")
    parts = pointer_parts(json_path)

    if op == "append":
        if parts:
            container, last = _walk(doc, parts)
            if isinstance(container, dict):
                current = container.get(last)
                if current is None:
                    container[last] = [value]
                elif isinstance(current, list):
                    current.append(value)
                else:
                    raise FixError(f"{json_path} is not an array")
            elif isinstance(container, list):
                current = container[_index(container, last)]
                if not isinstance(current, list):
                    raise FixError(f"{json_path} is not an array")
                current.append(value)
            else:
                raise FixError(f"{json_path} has no container")
        return doc

    if not parts:
        raise FixError("refusing to replace the whole document")
    container, last = _walk(doc, parts)
    if op == "remove":
        if isinstance(container, list):
            idx = _index(container, last)
            if idx < 0 or idx >= len(container):
                raise FixError(f"index out of range: {json_path}")
            del container[idx]
        elif isinstance(container, dict):
            if last not in container:
                raise FixError(f"key does not exist: {json_path}")
            del container[last]
        else:
            raise FixError(f"{json_path} has no container")
        return doc

    if op == "set":
        if isinstance(container, list):
            idx = _index(container, last)
            if idx < 0 or idx >= len(container):
                raise FixError(f"index out of range: {json_path}")
            container[idx] = value
        elif isinstance(container, dict):
            container[last] = value              # creates the key when it is missing
        else:
            raise FixError(f"{json_path} has no container")
        return doc

    # insert
    if not isinstance(value, dict) or "index" not in value:
        raise FixError("insert needs {'index': n, 'value': …}")
    item = value.get("value")
    if isinstance(container, list):
        container.insert(_index(container, str(value["index"])), item)
    elif isinstance(container, dict) and isinstance(container.get(last), list):
        container[last].insert(_index(container, str(value["index"])), item)
    else:
        raise FixError(f"{json_path} is not an array")
    return doc


def humanise(identifier: str) -> str:
    """`pct_change_24h` → `Pct change 24h`: the label a person would have written."""
    words = str(identifier).replace("_", " ").replace("-", " ").split()
    if not words:
        return str(identifier)
    text = " ".join(words)
    return text[:1].upper() + text[1:]
