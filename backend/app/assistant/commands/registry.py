"""The chat's Spec Kit commands (feature 021, plan §1 and §2): definitions, prompt files, parsing.

Descriptions and argument hints come from the front matter of each prompt file
(`bizview_cli/workspace_template/agent_commands/<locale>/<name>.md`), so the registry and the
prompt files are the single source of the `/` menu.
"""
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from app.errors import ApiError
from app.i18n import M

INSPECTION_TOOLS = frozenset({
    "list_sources", "describe_source", "profile_source", "get_workspace", "get_authoring_guide",
    "read_draft", "get_app_guide", "get_project_overview", "update_notes", "set_current_spec",
})


@dataclass(frozen=True)
class CommandDef:
    name: str
    needs_spec: bool
    needs_args: bool
    interactive: bool
    provider: bool
    tools: frozenset[str]
    writes: tuple[str, ...]
    reads: tuple[str, ...]
    prereqs: tuple[str, ...]


def _def(name, needs_spec, needs_args, interactive, provider, tools, writes, reads, prereqs):
    return name, CommandDef(name, needs_spec, needs_args, interactive, provider,
                            frozenset(tools), tuple(writes), tuple(reads), tuple(prereqs))


_ALL_DOCS = ("constitution", "spec", "plan", "tasks", "research", "data-model", "quickstart")

# Menu order (plan §1 table).
REGISTRY: dict[str, CommandDef] = dict([
    # 039: one command runs the whole plan. Its own run writes only the report and the decision
    # log; every stage is a real command run opened through `run_command` (028 FR-004).
    _def("speckit-all", False, True, False, True, {"edit_draft", "run_preview"},
         ["run_report", "decisions_append"], ["constitution", *_ALL_DOCS], []),
    _def("speckit-constitution", False, True, True, True, {"edit_draft"}, ["constitution"],
         ["constitution"], []),
    _def("speckit-specify", False, True, True, True, {"propose_draft", "edit_draft"},
         ["new_spec"], ["constitution"], []),
    _def("speckit-clarify", True, False, True, True, {"edit_draft"},
         ["spec_doc", "req_checklist_toggle"], ["constitution", "spec"], ["spec"]),
    _def("speckit-plan", True, False, False, True, {"propose_draft", "edit_draft"},
         ["plan_docs"], ["constitution", "spec"], ["spec"]),
    _def("speckit-tasks", True, False, False, True, {"edit_draft"}, ["tasks_doc"], _ALL_DOCS,
         ["plan"]),
    _def("speckit-analyze", True, False, False, True, set(), [],
         ["constitution", "spec", "plan", "tasks"], ["spec", "plan", "tasks"]),
    _def("speckit-checklist", True, False, True, True, {"edit_draft"}, ["custom_checklist"],
         ["constitution", "spec", "plan", "tasks"], ["spec"]),
    # A quick fix: correct an artifact that already exists without writing a new spec (the
    # product's own validation and preview still gate it, and nothing new can be created).
    _def("fix", False, True, True, True, {"edit_draft", "check_query", "run_preview"},
         ["existing_artifacts"], ["constitution", *_ALL_DOCS], []),
    _def("speckit-implement", True, False, True, True,
         {"propose_draft", "edit_draft", "check_query", "run_preview"},
         ["kind_artifacts", "tasks_ticks", "status_implemented"], _ALL_DOCS, ["tasks"]),
    _def("speckit-converge", True, False, False, True,
         {"edit_draft", "check_query", "run_preview"}, ["tasks_append"],
         ["constitution", "spec", "plan", "tasks"], ["spec", "plan", "tasks"]),
    # 039: the verify stage of `/speckit-all`, and a re-check on its own. Read-only by design, so
    # its verdicts are product-computed and nothing can be "fixed" by the stage that judges it.
    _def("speckit-verify", True, False, False, True, {"check_query", "run_preview"}, [],
         ["constitution", "spec", "plan", "tasks"], ["spec", "plan", "tasks"]),
    # 023: without arguments a fixed reply (no provider); with a topic, a read-only run.
    _def("ayuda", False, False, False, True, set(), [], [], []),
])

DOCS = {"spec": "spec.md", "plan": "plan.md", "tasks": "tasks.md", "research": "research.md",
        "data-model": "data-model.md", "quickstart": "quickstart.md"}

# A command's arguments are the message minus the command token, so they share the message
# ceiling (`service.MAX_USER_TEXT`, and the composer's own `maxLength`). A real brief is a
# page of text: the 4 000 of feature 021 refused the `coinmarketcap` panorama prompt at
# 7 629 characters (feature 039 defect fix). `test_commands_registry` keeps the two equal.
MAX_ARGS = 20000
MAX_BODY = 12 * 1024
PLACEHOLDERS = ("spec_template", "plan_template", "tasks_template")

_FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]*$")


def _dir(locale: str):
    return (resources.files("bizview_cli") / "workspace_template" / "agent_commands"
            / (locale if locale in ("es", "en") else "es"))


@lru_cache(maxsize=64)
def load(name: str, locale: str) -> tuple[dict, str]:
    """(front matter, body) of a command's prompt file."""
    text = (_dir(locale) / f"{name}.md").read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    front = _FRONT.match(text)
    if front:
        body = text[front.end():]
        for line in front.group(1).splitlines():
            key, sep, value = line.partition(":")
            if not sep or not key.strip():
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            meta[key.strip()] = value
    if len(body.encode("utf-8")) > MAX_BODY:
        raise ValueError(f"prompt body too long: {name} ({locale})")
    return meta, body


def _template(kind: str) -> str:
    return (resources.files("bizview_cli") / "workspace_template" / "preset" / "templates"
            / f"{kind}-template.md").read_text(encoding="utf-8")


def prompt_body(name: str, locale: str) -> str:
    """The command's prompt with the preset templates in place (strict placeholders)."""
    def fill(match: re.Match) -> str:
        key = match.group(1)
        if key not in PLACEHOLDERS:
            raise ValueError(f"unknown placeholder {key} in {name}")
        return _template(key.removesuffix("_template"))
    return _PLACEHOLDER.sub(fill, load(name, locale)[1])


def list_commands(locale: str) -> list[dict]:
    """The `/` menu in the request language."""
    out = []
    for name, definition in REGISTRY.items():
        meta = load(name, locale)[0]
        out.append({"name": name, "description": meta.get("description", ""),
                    "argument_hint": meta.get("argument_hint", ""),
                    "needs_spec": definition.needs_spec, "needs_args": definition.needs_args})
    return out


@dataclass(frozen=True)
class Parsed:
    name: str
    args: str
    definition: CommandDef


def parse(text: str) -> Parsed | None:
    """A command message (`/name args…`), None for plain text; API errors for bad commands."""
    s = text.lstrip()
    if not s.startswith("/") or s.startswith(("//", "/ ")):
        return None
    parts = re.split(r"\s", s[1:], maxsplit=1)
    token, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    if not _NAME.match(token):
        return None
    name = token.replace(".", "-").lower()
    args = rest.strip()
    if name not in REGISTRY:
        raise ApiError(422, "unknown_command",
                       M("commands.unknown", command=name,
                         commands=", ".join(f"/{n}" for n in REGISTRY)),
                       extra={"command": name, "commands": list(REGISTRY)})
    if len(args) > MAX_ARGS:
        raise ApiError(422, "command_args_too_long", M("commands.args_too_long", limit=MAX_ARGS),
                       extra={"limit": MAX_ARGS})
    definition = REGISTRY[name]
    if definition.needs_args and not args:
        raise ApiError(422, "command_needs_args",
                       M("commands.needs_args", command=name,
                         hint=load(name, "es")[0].get("argument_hint", "")),
                       extra={"command": name})
    return Parsed(name, args, definition)


def _help(locale: str) -> str:
    """Fixed `/ayuda` reply: the commands and what they do (023 replaces it with the guide)."""
    lines = []
    for cmd in list_commands(locale):
        if cmd["name"] == "ayuda":
            continue
        hint = f" {cmd['argument_hint']}" if cmd["argument_hint"] else ""
        lines.append(f"- `/{cmd['name']}`{hint} — {cmd['description']}")
    return "\n".join(lines)


HANDLERS: dict[str, Callable[[str], str]] = {"ayuda": _help}
