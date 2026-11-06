"""`bizview` command: init, project, validate, describe, import, theme, version."""
import argparse
import sys
from pathlib import Path

import yaml

from bizview_cli import __version__
from bizview_cli.i18n import t, use_lang


def _validate(args) -> int:
    from bizview_cli.describe import DescribeError, fetch, structure_from
    from bizview_cli.validate import (
        DirectContext,
        lock_differences,
        read_lock,
        validate,
        write_lock,
    )
    root = Path(args.path)
    if not args.describe and not args.live:
        result = validate(root)
    else:
        descriptions: dict[str, dict] = {}
        for value in args.describe or []:
            name, _, file = value.partition("=")
            name, file = name.strip(), file.strip()
            if not name or not file:
                print(t("cli.describe_expects_file", value=value), file=sys.stderr)
                return 2
            try:
                descriptions[name.lower()] = yaml.safe_load(Path(file).read_text("utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
                print(t("cli.read_failed", file=file, exc=type(e).__name__), file=sys.stderr)
                return 2
        live_cache: dict[str, dict] = {}
        live_errors: dict[str, str] = {}

        def structure(source: str, tables: list[str]) -> dict:
            key = source.strip().lower()
            if key in descriptions:
                return structure_from(descriptions[key], tables)
            if args.live:
                if key not in live_cache and key not in live_errors:
                    try:
                        live_cache[key] = fetch(source)
                    except DescribeError as e:
                        live_errors[key] = e.message
                if key in live_errors:
                    return {"tables": {}, "error": live_errors[key]}
                return structure_from(live_cache[key], tables)
            return {"tables": {},
                    "error": t("cli.no_source_description")}

        result = validate(root, direct=DirectContext(structure=structure))
    for issue in result.issues:
        label = t("cli.level_error") if issue.level == "error" else t("cli.level_warning")
        print(f"{label} {issue}", file=sys.stderr)
    if not result.ok:
        print(t("cli.validation_errors", count=sum(i.level == "error" for i in result.issues)),
              file=sys.stderr)
        return 1
    n_direct = sum("direct" in e.artifact for e in result.reports.values())
    summary = t("cli.summary_valid", integrations=len(result.integrations),
                reports=len(result.reports))
    if n_direct:
        if not args.describe and not args.live:
            summary += t("cli.summary_direct_unchecked", n=n_direct)
        elif any(i.code == "direct_structure_unchecked" for i in result.issues):
            summary += t("cli.summary_direct_partial", n=n_direct)
        else:
            summary += t("cli.summary_direct_checked", n=n_direct)
    print(summary)
    if result.layout == "v2":
        from bizview_cli import importer

        for slug in sorted(result.projects):
            print(t("cli.summary_project", project=slug,
                    integrations=sum(e.project == slug for e in result.integrations.values()),
                    reports=sum(e.project == slug for e in result.reports.values()),
                    distributions=sum(e.project == slug for e in result.distributions.values())))
            # Feature 049: the same two allowances the server applies, measured on the folder. It is
            # a report, not a failure: a project already applied must not turn "invalid" because an
            # installation later lowered a limit.
            measured = importer.measure(root / "projects" / slug)
            print(t("cli.budget_project_title", project=slug))
            print(importer.render_budgets(measured))
    if args.write_lock:
        path = write_lock(root, result.lock)
        print(t("cli.lock_written", path=path))
    else:
        current = read_lock(root)
        diffs = lock_differences(current or {}, result.lock) if current else [t("cli.no_lock")]
        if diffs:
            print(t("cli.lock_mismatch", diffs=", ".join(diffs)), file=sys.stderr)
            return 1
    return 0


def _run(args) -> int:
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "validate":
        return _validate(args)
    if args.command == "init":
        from bizview_cli.init import init
        return init(Path(args.path), args.name, agent=args.agent, git=not args.no_git,
                    layout=args.layout)
    if args.command == "import":
        return _import(args)
    if args.command == "theme":
        return _theme(args)
    if args.command == "project":
        from bizview_cli.project import new_project
        return new_project(Path(args.path), args.name, slug=args.slug, agent=args.agent,
                           speckit_init=not args.no_speckit)
    from bizview_cli.describe import describe
    return describe(args.source, path=args.path, as_json=args.json, pack=args.pack, out=args.out)


def _import(args) -> int:
    """Feature 049/055: measure a folder or a zip against both allowances and diff it against the
    workspace this command runs in. The app owns the upload: nothing here writes anything, and
    `--dry-run` says the same and writes nothing (it never does)."""
    import json

    from bizview_cli import importer

    try:
        result = importer.measure(Path(args.path))
    except importer.Unreadable as e:
        print(t("cli.read_failed", file=str(e), exc="unreadable"), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(importer.render(result))
    return 0 if result["importable"] else 1


def _theme(args) -> int:
    from bizview_cli.i18n import t
    from bizview_cli.theme import load_theme_text

    path = Path(args.file)
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        print(t("cli.theme_unreadable", path=str(path)), file=sys.stderr)
        return 2
    data, problems = load_theme_text(text)
    if problems:
        print(t("cli.theme_problems", count=len(problems)), file=sys.stderr)
        for problem in problems:
            print(f"  {problem.path}: {problem.message}", file=sys.stderr)
        return 1
    if args.theme_command == "validate":
        print(t("cli.theme_ok", id=data["id"], name=data["name"]))
        return 0

    from bizview_cli.theme_preview import preview_svg

    out = Path(args.out or f"{data['id']}-preview.svg")
    if out.suffix.lower() != ".svg":
        print(t("cli.theme_preview_format", suffix=out.suffix or out.name), file=sys.stderr)
        return 2
    out.write_text(preview_svg(data), "utf-8")
    print(t("cli.theme_preview_written", path=str(out)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bizview", description=t("cli.description"))
    parser.add_argument("--lang", choices=["es", "en"], default=None, help=t("cli.lang_help"))
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help=t("cli.validate_help"))
    v.add_argument("path", nargs="?", default=".")
    v.add_argument("--write-lock", action="store_true", help=t("cli.validate_write_lock_help"))
    v.add_argument("--describe", action="append", default=None, metavar="NOMBRE=ARCHIVO",
                   help=t("cli.validate_describe_help"))
    v.add_argument("--live", action="store_true",
                   help=t("cli.validate_live_help"))
    i = sub.add_parser("init", help=t("cli.init_help"))
    i.add_argument("path")
    i.add_argument("--name", required=True, help=t("cli.init_name_help"))
    i.add_argument("--agent", default="claude",
                   help=t("cli.init_agent_help"))
    i.add_argument("--no-git", action="store_true")
    i.add_argument("--layout", choices=["v2", "legacy"], default="v2",
                   help=t("cli.init_layout_help"))
    p = sub.add_parser("project", help=t("cli.project_help"))
    project_sub = p.add_subparsers(dest="project_command", required=True)
    n = project_sub.add_parser("new", help=t("cli.project_new_help"))
    n.add_argument("name")
    n.add_argument("--path", default=".", help=t("cli.project_path_help"))
    n.add_argument("--slug", help=t("cli.project_slug_help"))
    n.add_argument("--agent", default="claude", help=t("cli.init_agent_help"))
    n.add_argument("--no-speckit", action="store_true", help=t("cli.project_no_speckit_help"))
    d = sub.add_parser("describe", help=t("cli.describe_help"))
    d.add_argument("source", help=t("cli.describe_source_help"))
    d.add_argument("--path", help=t("cli.describe_path_help"))
    d.add_argument("--json", action="store_true")
    d.add_argument("--pack", action="store_true", help=t("cli.describe_pack_help"))
    d.add_argument("--out", default=".", help=t("cli.describe_out_help"))
    imp = sub.add_parser("import", help=t("cli.import_help"))
    imp.add_argument("path", help=t("cli.import_help"))
    imp.add_argument("--dry-run", action="store_true", help=t("cli.import_dry_run_help"))
    imp.add_argument("--json", action="store_true", help=t("cli.import_json_help"))
    th = sub.add_parser("theme", help=t("cli.theme_help"))
    theme_sub = th.add_subparsers(dest="theme_command", required=True)
    tv = theme_sub.add_parser("validate", help=t("cli.theme_validate_help"))
    tv.add_argument("file")
    tp = theme_sub.add_parser("preview", help=t("cli.theme_preview_help"))
    tp.add_argument("file")
    tp.add_argument("--out", help=t("cli.theme_preview_out_help"))
    sub.add_parser("version")
    args = parser.parse_args(argv)
    with use_lang(args.lang):
        return _run(args)


if __name__ == "__main__":
    sys.exit(main())
