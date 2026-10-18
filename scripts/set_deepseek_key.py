"""Set DEEPSEEK_API_KEY on this project's local `deepseek` MCP entry in ~/.claude.json.

The key is read with a hidden prompt (or from the DEEPSEEK_API_KEY env var),
never passed as an argument, so it stays out of shell history and process lists.
If the project has no `deepseek` entry yet, one is created using the npx found
on PATH (or the newest nvm Node), with PATH set in env for the nvm case.

    python scripts/set_deepseek_key.py            # prompt for the key
    python scripts/set_deepseek_key.py --check    # also verify it against the DeepSeek API

Close or restart Claude Code afterwards: a running session can rewrite
~/.claude.json and drop the change (re-run the script if that happens).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT = str(Path(__file__).resolve().parents[1])
SERVER = "deepseek"


def mask(key: str) -> str:
    return f"{key[:3]}…{key[-4:]} ({len(key)} chars)" if len(key) > 8 else "***"


def find_npx() -> Path:
    found = shutil.which("npx")
    if found:
        # absolute(), not resolve(): the npx symlink target (npm/bin/npx-cli.js)
        # sits in a directory without `node`, which the shebang needs on PATH.
        return Path(found).absolute()
    nvm = sorted((Path.home() / ".nvm/versions/node").glob("v*/bin/npx"),
                 key=lambda p: tuple(int(n) for n in p.parts[-3][1:].split(".")))
    if nvm:
        return nvm[-1]
    sys.exit("npx not found on PATH or under ~/.nvm; install Node.js first; config not changed")


def new_entry() -> dict:
    npx = find_npx()
    return {
        "type": "stdio",
        "command": str(npx),
        "args": ["-y", "@arikusi/deepseek-mcp-server"],
        "env": {
            "PATH": f"{npx.parent}:/usr/local/bin:/usr/bin:/bin",
            "REQUEST_TIMEOUT": "120000",
        },
    }


def check_key(key: str) -> None:
    req = urllib.request.Request(
        "https://api.deepseek.com/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            models = [m["id"] for m in json.load(resp).get("data", [])]
        print(f"check: key accepted by DeepSeek; models: {', '.join(models) or 'none listed'}")
    except urllib.error.HTTPError as e:
        sys.exit(f"check: DeepSeek rejected the key (HTTP {e.code}); config not changed")
    except urllib.error.URLError as e:
        sys.exit(f"check: could not reach DeepSeek ({e.reason}); config not changed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=str(Path.home() / ".claude.json"))
    ap.add_argument("--project", default=PROJECT)
    ap.add_argument("--check", action="store_true", help="verify the key with the DeepSeek API first")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    data = json.loads(cfg_path.read_text())
    servers = data.get("projects", {}).get(args.project, {}).get("mcpServers", {})
    entry = servers.get(SERVER)
    created = entry is None
    if created:
        entry = new_entry()

    key = os.environ.get("DEEPSEEK_API_KEY") or getpass.getpass("DeepSeek API key (hidden): ")
    key = key.strip()
    if not key or "REPLACE" in key:
        sys.exit("empty or placeholder key; config not changed")
    if not key.startswith("sk-"):
        print("warning: DeepSeek keys usually start with 'sk-'")
    if args.check:
        check_key(key)

    backup = cfg_path.with_name(f"{cfg_path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(cfg_path, backup)

    entry.setdefault("env", {})["DEEPSEEK_API_KEY"] = key
    if created:
        project = data.setdefault("projects", {}).setdefault(args.project, {})
        project.setdefault("mcpServers", {})[SERVER] = entry
    tmp = cfg_path.with_name(cfg_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, cfg_path)

    if created:
        print(f"created {SERVER} MCP entry (command: {entry['command']})")
    print(f"set {SERVER}.env.DEEPSEEK_API_KEY = {mask(key)}")
    print(f"project: {args.project}")
    print(f"backup:  {backup}")
    print("next: restart Claude Code, then check /mcp shows deepseek connected")


if __name__ == "__main__":
    main()
