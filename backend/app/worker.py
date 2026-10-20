"""Integration worker (feature 005, research R4): `python -m app.worker`.

Same image as the backend, another entry point. Schedules every integration of the ACTIVE
workspace version (its `schedule` for incremental runs, each dataset's `full_rebuild_cron` for
full runs) in the installation time zone, reloads when another version is applied or rolled
back, and runs the manual requests queued in `integration_run_request`.  Controls
(pause/resume, schedule overrides, allowed-hours windows) are re-read every loop and at fire
time (feature 013, US1/T003). On start it sweeps orphaned `running` rows left by a worker
that crashed without releasing its integration lock (feature 013, T009), and removes stale
whole-mode transform spill folders left by a crashed run (feature 005, T035).
It also delivers queued dashboard emails and scheduled email subscriptions (feature 018), and
rebuilds missing/outdated daily rollups when a new version is applied (feature 005, T038).
"""
import logging
import signal
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, text, update

from app.assistant import attachments
from app.assistant import preview as assistant_preview
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import direct, rollup, runner, schedule, transform
from app.i18n import M, to_stored
from app.mail import sends as mail_sends
from app.mail import subscriptions as mail_subscriptions
from app.models import (
    AppUser,
    AssistantAutoRun,
    AssistantMessage,
    AssistantPreviewRequest,
    AssistantSession,
    IntegrationControl,
    IntegrationRun,
    IntegrationRunRequest,
    WorkspaceVersion,
)
from app.security import crypto
from app.telegram import service as telegram
from app.telegram.poller import TelegramPoller

log = logging.getLogger("app.worker")
MAX_PARALLEL = 4
MAIL_EVERY = 15
SUBSCRIPTIONS_EVERY = 60


def cron(expr: str, tz: str) -> CronTrigger:
    return schedule.trigger(expr, tz)


def schedules(version: WorkspaceVersion,
              controls: dict[str, IntegrationControl] | None = None) -> list[tuple[str, str, str]]:
    """(integration id, kind, cron) for every scheduled run of a version, honouring overrides."""
    return schedule.schedules(version.artifacts, controls)


def next_run(expr: str, tz: str, now: datetime | None = None) -> datetime | None:
    return cron(expr, tz).get_next_fire_time(None, now or datetime.now(UTC))


def controls_fingerprint(db) -> tuple:
    """Ordered (integration_id, updated_at) tuple; used to detect control changes."""
    rows = db.scalars(select(IntegrationControl)).all()
    return tuple(sorted((c.integration_id, c.updated_at) for c in rows))


def _failed_checks(run) -> bool:
    """A run whose checks did not pass is a failure for the watch even if it loaded rows."""
    checks = getattr(run, "checks", None) or []
    return any(not item.get("ok", True) for item in checks if isinstance(item, dict))


def _notify_session(db, watch, reason) -> None:
    """A system message in the conversation that authorised the run (FR-008)."""
    from app.i18n import t

    session = db.get(AssistantSession, watch.session_id)
    if session is None:
        return
    detail = t("assistant.watch.failed", integration=watch.watch_integration or "-",
               reason=str(reason)[:200])
    if watch.watch_state == "rolled_back":
        detail += "\n" + t("assistant.watch.rolled_back")
    db.add(AssistantMessage(session_id=session.id, role="assistant", content=detail))
    session.updated_at = datetime.now(UTC)


class Worker:
    def __init__(self):
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler(timezone=self.settings.timezone,
                                             job_defaults={"coalesce": True, "max_instances": 1,
                                                           "misfire_grace_time": 300})
        self.pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL, thread_name_prefix="run")
        self.version_id: int | None = None
        self.loaded: tuple | None = None
        self.stop = threading.Event()
        self.last_telegram_purge: float | None = None
        self.last_preview_cleanup: float | None = None
        self.last_mail: float | None = None
        self.mail_job: Future | None = None
        self.last_subscriptions: float | None = None
        self.last_rollup: float | None = None
        self.rollup_job: Future | None = None
        self.rollup_pending = False
        self.rollup_version: int | None = None

    def run_scheduled(self, version_id: int, integration_id: str, kind: str,
                      now: datetime | None = None) -> None:
        with get_sessionmaker()() as db:
            version = db.get(WorkspaceVersion, version_id)
            if version is None or version.state != "active":
                return
            item = version.artifacts["integrations"].get(integration_id)
            if item is None:
                return
            control = db.get(IntegrationControl, integration_id)
            if control is not None:
                at = now or datetime.now(UTC)
                if control.paused:
                    log.info("integration %s is paused; skipping scheduled run", integration_id)
                    return
                if control.window_start is not None and not schedule.in_window(
                        control.window_start, control.window_end, at, self.settings.timezone):
                    log.info("integration %s outside allowed window; skipping scheduled run",
                             integration_id)
                    return
        run = runner.run_integration(item["definition"], item["files"], version_id=version_id,
                                     kind=kind)
        log.info("run %s %s %s: %s", run.id, integration_id, kind, run.status)
        if run.status in ("failed", "stopped") or _failed_checks(run):
            self._resolve_auto_watch(run, version_id, integration_id)

    def _resolve_auto_watch(self, run, version_id: int, integration_id: str) -> None:
        """Feature 028 (FR-008): the first scheduled run of an autonomous apply failed.

        The super user is told in the conversation and, with `auto_rollback`, the previous version
        comes back. A normal version switch: the scheduler reloads on its next loop.
        """
        from app.workspace import service as workspace_service

        with get_sessionmaker()() as db:
            watch = db.scalar(select(AssistantAutoRun).where(
                AssistantAutoRun.watch_state == "pending",
                AssistantAutoRun.version_id == version_id))
            if watch is None:
                return
            if watch.watch_integration and integration_id not in watch.watch_integration.split(","):
                return
            contract = watch.contract or {}
            rollback = bool(contract.get("auto_rollback", True))
            actor = db.get(AppUser, watch.confirmed_by)
            reason = run.message or run.status
            if rollback and actor is not None:
                try:
                    previous = workspace_service.rollback(db, actor, None)
                except Exception:  # a rollback that cannot run must not kill the worker
                    log.exception("auto rollback of version %s failed", version_id)
                    watch.watch_state = "failed"
                else:
                    watch.watch_state = "rolled_back"
                    watch.stop_reason = f"rolled_back:{run.id}"
                    log.warning("version %s rolled back to %s after run %s",
                                version_id, previous.id, run.id)
            else:
                watch.watch_state = "failed"
            _notify_session(db, watch, reason)
            db.commit()

    def reload(self) -> None:
        with get_sessionmaker()() as db:
            version = db.scalar(select(WorkspaceVersion).where(WorkspaceVersion.state == "active"))
            controls = {c.integration_id: c for c in db.scalars(select(IntegrationControl))}
            fingerprint = tuple(sorted((c.integration_id, c.updated_at)
                                       for c in controls.values()))
        vid = version.id if version else None
        key = (vid, fingerprint)
        if key == self.loaded:
            return
        self.scheduler.remove_all_jobs()
        self.loaded = key
        self.version_id = vid
        if version is None:
            log.info("no active workspace version; nothing scheduled")
            return
        for iid, kind, expr in schedules(version, controls):
            self.scheduler.add_job(self.run_scheduled, cron(expr, self.settings.timezone),
                                   args=(vid, iid, kind), id=f"{iid}:{kind}:{expr}")
        log.info("workspace version %s: %d scheduled runs", vid, len(self.scheduler.get_jobs()))

    def sweep_orphaned_runs(self) -> int:
        """Mark running rows as failed when no live worker holds their integration lock."""
        with get_sessionmaker()() as db:
            iids = db.scalars(select(IntegrationRun.integration_id).where(
                IntegrationRun.status == "running").distinct()).all()
        marked = 0
        for iid in iids:
            try:
                with get_sessionmaker().begin() as db:
                    acquired = db.scalar(text(
                        "SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
                        {"k": runner._lock_key(iid)})
                    if not acquired:
                        continue
                    restart_text, restart_key, _ = to_stored(M("run.worker_restarted"))
                    result = db.execute(update(IntegrationRun).where(
                        IntegrationRun.integration_id == iid,
                        IntegrationRun.status == "running").values(
                        status="failed",
                        finished_at=datetime.now(UTC),
                        message=restart_text, message_key=restart_key, message_params=None))
                    marked += result.rowcount or 0
            except Exception:
                log.exception("sweep_orphaned_runs: error for integration %s", iid)
        if marked:
            log.info("sweep_orphaned_runs: marked %d runs as failed", marked)
        return marked

    def take_requests(self) -> None:
        with get_sessionmaker().begin() as db:
            requests = list(db.scalars(
                select(IntegrationRunRequest).where(IntegrationRunRequest.taken_at.is_(None))
                .order_by(IntegrationRunRequest.id).with_for_update(skip_locked=True).limit(10)))
            for r in requests:
                r.taken_at = datetime.now(UTC)
            taken = [(r.id, r.integration_id, r.kind, r.requested_by) for r in requests]
        for request_id, iid, kind, user_id in taken:
            self.pool.submit(self._manual, request_id, iid, kind, user_id)

    def _manual(self, request_id: int, integration_id: str, kind: str, user_id: int | None):
        try:
            with get_sessionmaker()() as db:
                version = db.scalar(select(WorkspaceVersion)
                                    .where(WorkspaceVersion.state == "active"))
                item = (version.artifacts["integrations"].get(integration_id)
                        if version else None)
            if item is None:
                return
            run = runner.run_integration(item["definition"], item["files"],
                                         version_id=version.id, kind=f"manual_{kind}",
                                         requested_by=user_id)
            with get_sessionmaker().begin() as db:
                db.execute(update(IntegrationRunRequest)
                           .where(IntegrationRunRequest.id == request_id)
                           .values(run_id=run.id))
            log.info("manual run %s %s: %s", run.id, integration_id, run.status)
        except Exception:
            log.exception("manual run of %s failed", integration_id)

    def take_preview_requests(self) -> None:
        """Assistant previews (feature 014) run in the worker pool, like manual runs."""
        with get_sessionmaker().begin() as db:
            rows = list(db.scalars(
                select(AssistantPreviewRequest)
                .where(AssistantPreviewRequest.taken_at.is_(None))
                .order_by(AssistantPreviewRequest.id)
                .with_for_update(skip_locked=True)
                .limit(5)))
            for r in rows:
                r.taken_at = datetime.now(UTC)
            ids = [r.id for r in rows]
        for rid in ids:
            self.pool.submit(assistant_preview.process_request, rid)

    def preview_housekeeping(self) -> None:
        """Drop assistant preview schemas older than a day and prune direct-read logs,
        at most once per hour."""
        now = time.monotonic()
        if self.last_preview_cleanup is None or now - self.last_preview_cleanup >= 3600:
            with get_sessionmaker().begin() as db:
                assistant_preview.cleanup_stale(db)
            try:
                with get_sessionmaker().begin() as db:
                    direct.prune_log(db)
            except Exception:
                log.exception("direct read log pruning failed")
            try:
                # Feature 024: an image uploaded but never sent does not stay forever.
                with get_sessionmaker().begin() as db:
                    removed = attachments.sweep_pending(db)
                if removed:
                    log.info("removed %d pending chat attachments", removed)
            except Exception:
                log.exception("pending attachment sweep failed")
            self.last_preview_cleanup = now

    def take_email_sends(self, force: bool = False) -> Future | None:
        now = time.monotonic()
        if not force and (
            self.last_mail is not None and now - self.last_mail < MAIL_EVERY
        ):
            return None
        if self.mail_job is not None and not self.mail_job.done():
            return None
        self.last_mail = now
        self.mail_job = self.pool.submit(self._deliver_mail)
        return self.mail_job

    def _deliver_mail(self) -> int:
        try:
            handled = mail_sends.process_due()
            if handled:
                log.info("email: %d deliveries handled", handled)
            return handled
        except Exception:
            log.exception("email delivery failed")
            return 0

    def rollups_tick(self, force: bool = False) -> Future | None:
        """Ensure the active version's rollups exist and are fresh, at most once per version
        change or 60 s while pending (or on force)."""
        now = time.monotonic()
        new_version = self.version_id != self.rollup_version
        if (
            not force
            and not new_version
            and not (
                self.rollup_pending
                and (self.last_rollup is not None and now - self.last_rollup >= 60)
            )
        ):
            return None
        if self.rollup_job is not None and not self.rollup_job.done():
            return None
        self.last_rollup = now
        self.rollup_version = self.version_id
        self.rollup_job = self.pool.submit(self._ensure_rollups)
        return self.rollup_job

    def _ensure_rollups(self) -> bool:
        try:
            pending = rollup.ensure_version(self.version_id)
            self.rollup_pending = pending
            return pending
        except Exception:
            log.exception("rollup ensure failed")
            self.rollup_pending = True
            return False

    def email_subscriptions_tick(
        self, now: datetime | None = None, force: bool = False
    ) -> int:
        current = time.monotonic()
        if not force and (
            self.last_subscriptions is not None
            and current - self.last_subscriptions < SUBSCRIPTIONS_EVERY
        ):
            return 0
        self.last_subscriptions = current
        created = 0
        try:
            with get_sessionmaker().begin() as db:
                created = mail_subscriptions.tick(db, now)
            if created:
                log.info("email subscriptions: %d sends queued", created)
                self.take_email_sends(force=True)
        except Exception:
            log.exception("email subscription tick failed")
        return created

    def serve(self) -> None:
        with get_sessionmaker()() as db:
            crypto.verify_key_at_start(db, crypto.get_keyring())
        try:
            self.sweep_orphaned_runs()
        except Exception:
            log.exception("worker sweep failed; continuing")
        try:
            removed = transform.sweep_spill_dir()
            if removed:
                log.info("removed %d stale transform spill folders", removed)
        except Exception:
            log.exception("transform spill sweep failed; continuing")
        self.scheduler.start()
        poller = TelegramPoller(self.stop)   # feature 007: reads bot updates when enabled
        poller.start()
        log.info("worker started (time zone %s)", self.settings.timezone)
        while not self.stop.is_set():
            try:
                self.reload()
                self.rollups_tick()
                self.take_requests()
                self.take_preview_requests()
                self.telegram_housekeeping()
                self.preview_housekeeping()
                self.email_subscriptions_tick()
                self.take_email_sends()
            except Exception:
                log.exception("worker loop error")
            self.stop.wait(self.settings.worker_poll_seconds)
        self.scheduler.shutdown(wait=True)
        poller.join(timeout=40)
        self.pool.shutdown(wait=True)

    def telegram_housekeeping(self) -> None:
        """Expire due Telegram requests every loop; purge old ones at most once per hour."""
        with get_sessionmaker().begin() as db:
            telegram.expire_due(db)
            if (self.last_telegram_purge is None
                    or self.last_telegram_purge < time.monotonic() - 3600):
                telegram.purge_old(db)
                self.last_telegram_purge = time.monotonic()


def main() -> int:
    logging.basicConfig(level=get_settings().log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    worker = Worker()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.stop.set())
    worker.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
