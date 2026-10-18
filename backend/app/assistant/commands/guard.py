"""Server-side limits of a chat turn (feature 021, plan §3): which tools it may call and which
project files a /speckit-… command may change. The prompt asks; this module enforces.

All ops of a call are checked before anything is written (the caller writes only when
`check_ops` returns), so a refused op leaves the project untouched.
"""
import functools
import re
from dataclasses import dataclass
from importlib import resources

from app.assistant.commands.registry import INSPECTION_TOOLS, CommandDef
from app.i18n import M

WRITERS = frozenset({"propose_draft", "edit_draft"})
PROTECTED = re.compile(
    r"<!-- bizview:reglas-instalacion -->.*?<!-- /bizview:reglas-instalacion -->", re.S)
CONSTITUTION = ".specify/memory/constitution.md"
_NEW_SPEC = re.compile(
    r"^specs/(?P<num>\d{3})-(?P<short>[a-z0-9]+(?:-[a-z0-9]+){0,5})/"
    r"(?:spec\.md|checklists/requirements\.md)$")
_CHECKBOX = re.compile(r"^(\s*[-*]\s+)\[([ xX])\](.*)$")
_STATUS = re.compile(r"^\s*[-*]?\s*\*\*Status\*\*:\s*(.*?)\s*$")
_PLAN_IDS = (re.compile(r"`(?:integrations|reports)/([a-z0-9][a-z0-9-]*)/"),
             re.compile(r"`distributions/([a-z0-9][a-z0-9-]*)\.yaml`"))
_KIND_PATHS = {
    "integracion": r"integrations/(?P<id>[a-z0-9][a-z0-9-]*)/"
                   r"(?:integration\.yaml|queries/[^/]+\.sql|requests/[^/]+\.yaml)",
    "reporte": r"reports/(?P<id>[a-z0-9][a-z0-9-]*)/report\.yaml",
    "distribucion": r"distributions/(?P<id>[a-z0-9][a-z0-9-]*)\.yaml",
}
_KIND_HINTS = {
    "integracion": "integrations/<{ids}>/integration.yaml|queries/*.sql|requests/*.yaml",
    "reporte": "reports/<{ids}>/report.yaml",
    "distribucion": "distributions/<{ids}>.yaml",
}


class GuardError(Exception):
    """A refused tool or file change; `message` is a catalogue message for the agent."""

    def __init__(self, code: str, params: dict, message) -> None:
        super().__init__(str(message))
        self.code, self.params, self.message = code, params, message

    def __str__(self) -> str:
        return str(self.message)


def allowed_tools(definition: CommandDef | None) -> frozenset[str]:
    """Plain messages inspect and suggest; a command adds its tools and `finish_command`."""
    if definition is None:
        return INSPECTION_TOOLS | {"suggest_command"}
    return INSPECTION_TOOLS | definition.tools | {"finish_command"}


def check_tool(definition: CommandDef | None, tool: str) -> None:
    allowed = allowed_tools(definition)
    if tool in allowed:
        return
    if definition is None and tool in WRITERS:
        raise GuardError("write_needs_command", {"tool": tool}, M("commands.write_needs_command"))
    names = ", ".join(sorted(allowed))
    command = definition.name if definition else ""
    raise GuardError("tool_not_allowed",
                     {"tool": tool, "command": command, "allowed": sorted(allowed)},
                     M("commands.tool_not_allowed", tool=tool, command=command, allowed=names))


@dataclass(frozen=True)
class Context:
    definition: CommandDef
    spec: str | None                 # "003-ventas"; None until /speckit-specify writes it
    kind: str | None                 # **Tipo** of the spec
    reserved_number: int | None      # /speckit-specify
    plan_text: str
    installation_block: str          # protected block of the installation template
    files: dict[str, str]            # current project files


def protected_block(text: str) -> str:
    match = PROTECTED.search(text)
    return match.group(0) if match else ""


@functools.lru_cache(maxsize=1)
def installation_block() -> str:
    """The block every project constitution must keep byte-identical (plan §3): the one of the
    installation template, not the project's current file, which may have lost it."""
    template = (resources.files("bizview_cli") / "workspace_template" / "files"
                / "constitution.md")
    return protected_block(template.read_text(encoding="utf-8"))


def _lines_changed(old: str, new: str) -> list[tuple[str, str]] | None:
    """Changed (old, new) line pairs, None when the line count differs."""
    a, b = old.splitlines(), new.splitlines()
    if len(a) != len(b):
        return None
    return [(x, y) for x, y in zip(a, b, strict=True) if x != y]


def _artifact_ids(ctx: Context) -> set[str]:
    ids = {ctx.spec.split("-", 1)[1]} if ctx.spec and "-" in ctx.spec else set()
    for pattern in _PLAN_IDS:
        ids.update(pattern.findall(ctx.plan_text))
    return ids


class _Checker:
    """One call's state: the spec folder a /speckit-specify write establishes."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.new_folder: str | None = ctx.spec
        self.ids = _artifact_ids(ctx)

    def _doc(self, name: str) -> str | None:
        return f"specs/{self.ctx.spec}/{name}" if self.ctx.spec else None

    def constitution(self, op: dict) -> bool:
        if op["op"] != "write" or op["path"] != CONSTITUTION:
            return False
        block = self.ctx.installation_block
        return bool(block) and protected_block(op["content"]) == block

    def new_spec(self, op: dict) -> bool:
        m = _NEW_SPEC.match(op["path"])
        if op["op"] != "write" or not m or len(m.group("short")) > 40:
            return False
        if self.ctx.reserved_number is None or int(m.group("num")) != self.ctx.reserved_number:
            return False
        folder = f"{m.group('num')}-{m.group('short')}"
        if self.new_folder is not None:      # fixed by an earlier write of this run or call
            return folder == self.new_folder
        if any(p.startswith(f"specs/{folder}/") for p in self.ctx.files):
            return False                     # the folder must be new
        self.new_folder = folder
        return True

    def spec_doc(self, op: dict) -> bool:
        return op["op"] == "write" and op["path"] == self._doc("spec.md")

    def req_checklist_toggle(self, op: dict) -> bool:
        path = self._doc("checklists/requirements.md")
        if op["op"] != "write" or op["path"] != path or path not in self.ctx.files:
            return False
        changed = _lines_changed(self.ctx.files[path], op["content"])
        if changed is None:
            return False
        for old, new in changed:
            a, b = _CHECKBOX.match(old), _CHECKBOX.match(new)
            if not (a and b and a.group(1) == b.group(1) and a.group(3) == b.group(3)):
                return False
        return True

    def plan_docs(self, op: dict) -> bool:
        return op["op"] == "write" and op["path"] in {
            self._doc(n) for n in ("plan.md", "research.md", "data-model.md", "quickstart.md")}

    def tasks_doc(self, op: dict) -> bool:
        return op["op"] == "write" and op["path"] == self._doc("tasks.md")

    def custom_checklist(self, op: dict) -> bool:
        if op["op"] != "write" or not self.ctx.spec:
            return False
        m = re.fullmatch(rf"specs/{re.escape(self.ctx.spec)}/checklists/"
                         r"(?P<name>[a-z0-9][a-z0-9-]{0,40})\.md", op["path"])
        if not m or m.group("name") == "requirements":
            return False
        old = self.ctx.files.get(op["path"])
        return old is None or op["content"].startswith(old)

    def kind_artifacts(self, op: dict) -> bool:
        pattern = _KIND_PATHS.get(self.ctx.kind or "")
        m = re.fullmatch(pattern, op["path"]) if pattern and self.ctx.spec else None
        if not m or m.group("id") not in self.ids:
            return False
        return op["op"] == "write" or (op["op"] == "delete" and op["path"] in self.ctx.files)

    def tasks_ticks(self, op: dict) -> bool:
        path = self._doc("tasks.md")
        if op["op"] != "write" or op["path"] != path or path not in self.ctx.files:
            return False
        changed = _lines_changed(self.ctx.files[path], op["content"])
        return changed is not None and all(
            "- [ ]" in old and new in (old.replace("- [ ]", "- [X]", 1),
                                       old.replace("- [ ]", "- [x]", 1))
            for old, new in changed)

    def status_implemented(self, op: dict) -> bool:
        path = self._doc("spec.md")
        if op["op"] != "write" or op["path"] != path or path not in self.ctx.files:
            return False
        changed = _lines_changed(self.ctx.files[path], op["content"])
        if not changed:
            return False
        for old, new in changed:
            a, b = _STATUS.match(old), _STATUS.match(new)
            if not (a and b and b.group(1).lower() == "implemented"):
                return False
        return True

    def tasks_append(self, op: dict) -> bool:
        path = self._doc("tasks.md")
        if op["op"] != "write" or op["path"] != path or path not in self.ctx.files:
            return False
        return op["content"].startswith(self.ctx.files[path].rstrip("\n") + "\n")

    def hints(self) -> list[str]:
        ctx, spec = self.ctx, self.ctx.spec or "<spec>"
        out: list[str] = []
        for rule in ctx.definition.writes:
            if rule == "constitution":
                out.append(CONSTITUTION)
            elif rule == "new_spec":
                n = f"{ctx.reserved_number:03d}" if ctx.reserved_number is not None else "NNN"
                out += [f"specs/{n}-<nombre>/spec.md",
                        f"specs/{n}-<nombre>/checklists/requirements.md"]
            elif rule in ("spec_doc", "status_implemented"):
                out.append(f"specs/{spec}/spec.md")
            elif rule == "req_checklist_toggle":
                out.append(f"specs/{spec}/checklists/requirements.md")
            elif rule == "plan_docs":
                out.append(f"specs/{spec}/plan.md|research.md|data-model.md|quickstart.md")
            elif rule in ("tasks_doc", "tasks_ticks", "tasks_append"):
                out.append(f"specs/{spec}/tasks.md")
            elif rule == "custom_checklist":
                out.append(f"specs/{spec}/checklists/<nombre>.md")
            elif rule == "kind_artifacts" and ctx.kind in _KIND_HINTS:
                out.append(_KIND_HINTS[ctx.kind].format(ids="|".join(sorted(self.ids))))
        return list(dict.fromkeys(out))


def check_ops(ctx: Context, ops: list[dict]) -> str | None:
    """Refuse (GuardError) the first op no enabled rule accepts; return the spec folder a
    /speckit-specify write established (None otherwise)."""
    checker = _Checker(ctx)
    for op in ops:
        rules = [getattr(checker, rule) for rule in ctx.definition.writes]
        if not any(rule(op) for rule in rules):
            hints = checker.hints()
            raise GuardError(
                "path_not_allowed",
                {"path": op.get("path", ""), "command": ctx.definition.name, "allowed": hints},
                M("commands.path_not_allowed", command=ctx.definition.name,
                  path=op.get("path", ""), allowed=", ".join(hints)))
    return checker.new_folder if checker.new_folder != ctx.spec else None
