#!/usr/bin/env python3
"""Run the project locally: backend (FastAPI, auto-reload) + integration worker + frontend (Vite).

    python starter.py                 # install if needed, migrate, start both
    python starter.py --skip-migrate  # start without running migrations / bootstrap
    python starter.py --install       # force reinstall of backend and frontend dependencies
    python starter.py --backend-only  # or --frontend-only
    python starter.py --no-worker     # without the integration worker (feature 005)

Open http://localhost:5173 — Vite proxies /api to the backend, so the session cookie works as in
production. Settings come from .env (DATABASE_URL_BI, SUPER_USER_*, ...); the database is always
external. The workspace (vibe reporting) is read from WORKSPACE_PATH. Ctrl+C stops everything.

Requires: uv (Python) and Node.js 20+ with npm. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
IS_WINDOWS = os.name == "nt"

COLORS = {"backend": "\033[36m", "frontend": "\033[35m", "starter": "\033[34m"}
RESET = "\033[0m"
USE_COLOR = sys.stdout.isatty() and not IS_WINDOWS or os.environ.get("FORCE_COLOR")


def say(name: str, message: str) -> None:
    label = f"[{name:<8}]"
    if USE_COLOR:
        label = f"{COLORS.get(name, '')}{label}{RESET}"
    print(f"{label} {message}", flush=True)


def fail(message: str) -> None:
    say("starter", f"ERROR: {message}")
    sys.exit(1)


def child_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)  # let uv use backend/.venv without warnings
    env.update(extra)
    return env


def run_step(name: str, cmd: list[str], cwd: Path, **env: str) -> None:
    say(name, "$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd, env=child_env(**env))
    if result.returncode != 0:
        fail(f"'{' '.join(cmd)}' failed with exit code {result.returncode}")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_http(url: str, timeout: float, proc: subprocess.Popen) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def check_prerequisites(args: argparse.Namespace) -> tuple[str, str]:
    if not (ROOT / ".env").exists():
        fail(".env not found at the repository root (copy .env.example and fill it in)")
    uv = shutil.which("uv")
    npm = shutil.which("npm.cmd" if IS_WINDOWS else "npm") or shutil.which("npm")
    if not args.frontend_only and not uv:
        fail("uv is not installed: https://docs.astral.sh/uv/getting-started/installation/")
    if not args.backend_only and not npm:
        fail("npm is not installed: install Node.js 20+ (https://nodejs.org)")
    for port, what, skip in ((args.backend_port, "backend", args.frontend_only),
                             (args.frontend_port, "frontend", args.backend_only)):
        if not skip and not port_free(port):
            fail(f"port {port} for the {what} is already in use (choose another with "
                 f"--{what}-port)")
    return uv or "uv", npm or "npm"


def install(args: argparse.Namespace, uv: str, npm: str) -> None:
    if not args.frontend_only and (args.install or not (BACKEND / ".venv").exists()):
        run_step("backend", [uv, "sync"], BACKEND)
    if not args.backend_only and (args.install or not (FRONTEND / "node_modules").exists()):
        lock = (FRONTEND / "package-lock.json").exists()
        run_step("frontend", [npm, "ci" if lock else "install", "--no-audit", "--no-fund"],
                 FRONTEND)


def migrate(uv: str) -> None:
    say("backend", "migrating DATABASE_URL_BI and ensuring the super user exists")
    run_step("backend", [uv, "run", "alembic", "upgrade", "head"], BACKEND)
    run_step("backend", [uv, "run", "python", "-m", "app.cli", "bootstrap"], BACKEND)


class Service:
    def __init__(self, name: str, cmd: list[str], cwd: Path, env: dict[str, str]):
        self.name = name
        popen_kw: dict = {}
        if IS_WINDOWS:
            popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kw["start_new_session"] = True  # own process group: stop children too
        say(name, "$ " + " ".join(cmd))
        self.proc = subprocess.Popen(
            cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, **popen_kw)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            say(self.name, line.rstrip())

    def stop(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if IS_WINDOWS:
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=10)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            if not IS_WINDOWS:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                self.proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--skip-migrate", action="store_true",
                        help="do not run alembic upgrade / super-user bootstrap")
    parser.add_argument("--install", action="store_true", help="force dependency install")
    only = parser.add_mutually_exclusive_group()
    only.add_argument("--backend-only", action="store_true")
    only.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--no-worker", action="store_true", help="do not run the worker")
    args = parser.parse_args()

    uv, npm = check_prerequisites(args)
    install(args, uv, npm)
    if not args.frontend_only and not args.skip_migrate:
        migrate(uv)

    services: list[Service] = []
    stopping = threading.Event()

    def shutdown(*_: object) -> None:
        if stopping.is_set():
            return
        stopping.set()
        say("starter", "stopping…")
        for svc in reversed(services):
            svc.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    backend_url = f"http://localhost:{args.backend_port}"
    if not args.frontend_only:
        services.append(Service("backend", [
            uv, "run", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1",
            "--port", str(args.backend_port)], BACKEND,
            child_env(COOKIE_SECURE="false", DOCS_ENABLED=os.environ.get("DOCS_ENABLED", "true"))))
        if not wait_http(f"{backend_url}/api/health", 60, services[-1].proc):
            shutdown()
            fail("the backend did not become healthy (see its output above)")
        if not args.no_worker:
            services.append(Service("worker", [uv, "run", "python", "-m", "app.worker"],
                                    BACKEND, child_env()))

    if not args.backend_only:
        services.append(Service("frontend", [
            npm, "run", "dev", "--", "--port", str(args.frontend_port), "--strictPort"],
            FRONTEND, child_env(API_TARGET=backend_url)))
        if not wait_http(f"http://localhost:{args.frontend_port}/", 60, services[-1].proc):
            shutdown()
            fail("the frontend did not start (see its output above)")

    if not args.backend_only:
        say("starter", f"ready → http://localhost:{args.frontend_port}   (Ctrl+C to stop)")
    if not args.frontend_only:
        say("starter", f"API → {backend_url}/api   docs → {backend_url}/api/docs")

    # Stay up until Ctrl+C or until one of the services exits on its own.
    while not stopping.is_set():
        for svc in services:
            code = svc.proc.poll()
            if code is not None:
                say("starter", f"{svc.name} exited with code {code}")
                shutdown()
                return code or 1
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
