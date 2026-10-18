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
              ("AGENTS.md", "AGENTS.md"),
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
    if git:
        _git(path)
    print(t("init.done" if layout == "legacy" else "init.done_v2", name=name, path=path))
    return 0
