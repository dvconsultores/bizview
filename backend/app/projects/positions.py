"""Line numbers of validation problems (feature 020, research R14)."""

import re

import yaml


def line_for(text: str, pointer: str | None) -> int | None:
    """Return the 1-based line for an RFC 6901 pointer in YAML/JSON text."""
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return None
    if root is None:
        return None
    pointer = pointer or ""
    parts = [] if pointer == "" else pointer.lstrip("/").split("/")
    node = root
    deepest_line = root.start_mark.line + 1
    for raw in parts:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, yaml.MappingNode):
            found = next(((k, v) for k, v in node.value if k.value == part), None)
            if found is None:
                return deepest_line
            deepest_line = found[0].start_mark.line + 1
            node = found[1]
        elif isinstance(node, yaml.SequenceNode):
            try:
                node = node.value[int(part)]
            except (ValueError, IndexError):
                return deepest_line
            deepest_line = node.start_mark.line + 1
        else:
            return deepest_line
    return deepest_line


_MARKDOWN = {
    "status": re.compile(r"^\s*\*\*Status\*\*:", re.I),
    "kind": re.compile(r"^\s*[-*]?\s*\*\*(?:Tipo|Type|Spec type)\*\*:", re.I),
    "open_task": re.compile(r"^\s*- \[ \]"),
}


def markdown_line(text: str, marker: str) -> int | None:
    """Return the 1-based line matching a predefined markdown marker."""
    pattern = _MARKDOWN.get(marker)
    if pattern is None:
        return None
    for i, line in enumerate(text.splitlines(), 1):
        if pattern.match(line):
            return i
    return None


MARKDOWN_MARKERS = {
    "spec_not_approved": "status",
    "spec_kind_missing": "kind",
    "spec_incomplete": "kind",
    "open_tasks": "open_task",
}


def problem_line(problem: dict, text: str | None) -> int | None:
    """Return the line number for a validation problem."""
    if text is None:
        return None
    file = problem.get("file") or ""
    if file.endswith(".md"):
        marker = MARKDOWN_MARKERS.get(problem.get("code"))
        return markdown_line(text, marker) if marker else None
    if file.endswith((".yaml", ".yml", ".json")):
        return line_for(text, problem.get("path"))
    return None
