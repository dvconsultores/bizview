"""`bizview init`: a new customer workspace with Spec Kit + the Bizview preset and extension."""
import re
import shutil
import subprocess
import sys
from datetime import date
from importlib import resources
from pathlib import Path

from bizview_cli.i18n import t

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")


def _specify() -> list[str]:
    exe = shutil.which("specify")
    if exe:
        return [exe]
    if shutil.which("uvx"):
        return ["uvx", "--from", "specify-cli", "specify"]
    raise SystemExit(t("init.not_installed"))


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-2000:] + result.stderr[-2000:])
        raise SystemExit(t("init.failed", cmd=" ".join(cmd[:4]), code=result.returncode))


def _template() -> Path:
    return Path(str(resources.files("bizview_cli") / "workspace_template"))


def _check(path: Path, name: str) -> Path | None:
    if not NAME_RE.match(name):
        print(t("init.bad_name"), file=sys.stderr)
        return None
    path = path.resolve()
    if path.exists() and any(path.iterdir()):
        print(t("init.not_empty", path=path), file=sys.stderr)
        return None
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, values: dict, pairs: tuple[tuple[str, str], ...]) -> None:
    files = _template() / "files"
    for src, dst in pairs:
        target = path / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((files / src).read_text(encoding="utf-8").format(**values),
                          encoding="utf-8")


def _append(target: Path, src: str, sep: str = "") -> None:
    text = (_template() / "files" / src).read_text(encoding="utf-8")
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(current + (sep if current else "") + text, encoding="utf-8")


def _schemas(path: Path) -> None:
    schemas = path / ".bizview" / "schemas"
    schemas.mkdir(parents=True, exist_ok=True)
    for f in (resources.files("bizview_cli") / "schemas").iterdir():
        if f.name.endswith(".json"):
            (schemas / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")


def _git(path: Path) -> None:
    if shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=path, check=False)
        subprocess.run(["git", "add", "-A"], cwd=path, check=False)
        committed = subprocess.run(["git", "commit", "-q", "-m", t("init.commit_message")],
                                   cwd=path, capture_output=True).returncode == 0
        if not committed:
            print(t("init.git_hint"))


def speckit(path: Path, agent: str) -> None:
    """Spec Kit + the Bizview preset and extension in `path` (workspace or project folder)."""
    tpl = _template()
    specify = _specify()
    print("→ Spec Kit…")
    _run([*specify, "init", "--here", "--force", "--integration", agent, "--script", "sh",
          "--non-interactive", "--ignore-agent-tools"], path)
    print(t("init.preset"))
    _run([*specify, "preset", "add", "--dev", str(tpl / "preset")], path)
    _run([*specify, "extension", "add", str(tpl / "extension"), "--dev"], path)


ROOT_FILES = (("README.md", "README.md"), ("bizview.yaml", "bizview.yaml"),
              ("AGENTS.md", "AGENTS.md"), ("THEME.md", "THEME.md"),
              (".github/copilot-instructions.md", ".github/copilot-instructions.md"))


def init(path: Path, name: str, *, agent: str = "claude", git: bool = True,
         layout: str = "v2") -> int:
    """New workspace. v2 (feature 020): root files and `projects/`; each BI project gets its
    own Spec Kit with `bizview project new`. legacy: the 005 flat tree with Spec Kit at the root."""
    checked = _check(path, name)
    if checked is None:
        return 2
    path = checked
    values = {"name": name, "date": date.today().isoformat()}
    if layout == "legacy":
        speckit(path, agent)
        _write(path, values, (*ROOT_FILES,
                              ("constitution.md", ".specify/memory/constitution.md")))
        _append(path / "CLAUDE.md", "CLAUDE.md", "\n\n")
        folders = ("specs/integrations", "specs/reports", "integrations", "reports")
    else:
        _write(path, values, ROOT_FILES)
        _append(path / "CLAUDE.md", "CLAUDE.md", "\n\n")
        folders = ("projects",)
    _append(path / ".gitignore", "gitignore")
    _schemas(path)
    for d in folders:
        (path / d).mkdir(parents=True, exist_ok=True)
        (path / d / ".gitkeep").touch()
    if layout != "legacy":
        # Feature 057: what `bizview init workspace` writes is the starter pack, so the folder on
        # disk, the server's download and the published template share one source.
        _starter(path / "projects", name, lang="es", kind="integration", source=None)
    if git:
        _git(path)
    print(t("init.done" if layout == "legacy" else "init.done_v2", name=name, path=path))
    return 0


def _write_pack(target: Path, files: dict[str, str], *, manifest: bool) -> None:
    for rel, text in files.items():
        if rel == "bizview.yaml" and not manifest:
            continue
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _starter(parent: Path, name: str, *, lang: str, kind: str, source: str | None) -> Path:
    from bizview_cli import starter

    files = starter.render(name=name, lang=lang, kind=kind, source=source)
    target = parent / starter.plain_slug(name)
    target.mkdir(parents=True, exist_ok=True)
    _write_pack(target, files, manifest=False)
    return target


def init_project(name: str, *, source: str | None = None, lang: str = "es",
                 kind: str = "integration", directory: str | None = None) -> int:
    """`bizview init project <name>`: the starter pack as a project folder (feature 057).

    Inside a workspace (a folder with `bizview.yaml`) it goes to `projects/<slug>/`; anywhere else
    it goes to `./<slug>/` and carries its own `bizview.yaml`, so `bizview validate .` works from
    inside it. `--source` only fills the source's name in the skeletons — the structure document of
    a registered source is downloaded from the product, the only side that can read it."""
    from bizview_cli import starter

    name = name.strip()
    if not name:
        print(t("init.bad_name"), file=sys.stderr)
        return 2
    cwd = Path.cwd()
    inside = (cwd / "bizview.yaml").is_file()
    base = Path(directory).expanduser() if directory else (cwd / "projects" if inside else cwd)
    target = base / starter.plain_slug(name)
    if target.exists() and any(target.iterdir()):
        print(t("init.not_empty", path=target), file=sys.stderr)
        return 2
    try:
        files = starter.render(name=name, lang=lang, kind=kind, source=source)
    except starter.PackError as e:
        print(str(e), file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    _write_pack(target, files, manifest=not inside and directory is None)
    print(t("init.project_done", name=name, path=target))
    print(t("init.project_next", path=target))
    return 0
