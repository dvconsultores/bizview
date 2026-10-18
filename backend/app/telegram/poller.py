"""Background poller for Telegram updates (feature 007, contracts/bot.md "Polling").

Runs in the worker: long-polls getUpdates only while sign-in is available, one transaction per
update, offset persisted so a restart never replays an update. Update content is never logged.
"""

from __future__ import annotations

import logging
import threading

from app.db import get_sessionmaker
from app.telegram import service
from app.telegram.client import TelegramError
from app.telegram.handler import handle_update

log = logging.getLogger(__name__)


class TelegramPoller(threading.Thread):
    """Long-running thread polling getUpdates; one transaction per update."""

    def __init__(
        self,
        stop: threading.Event,
        *,
        sessionmaker=get_sessionmaker,
        idle_seconds: float = 10.0,
    ) -> None:
        super().__init__(name="telegram", daemon=True)
        self.stop = stop
        self.sessionmaker = sessionmaker
        self.idle_seconds = idle_seconds
        self._backoff = 1.0

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                if not self.poll_once():
                    self.stop.wait(self.idle_seconds)
            except Exception:
                log.exception("telegram poller error")
                self._sleep_backoff()

    def poll_once(self) -> bool:
        """One polling cycle. Returns True when Telegram was contacted."""
        with self.sessionmaker().begin() as db:
            row = service.settings_row(db)
            if not service.is_available(row):
                return False
            token = service.token_of(row)
            offset = row.update_offset

        bot = service.client_factory(token)
        try:
            try:
                updates = bot.get_updates(offset, timeout=25)
            except TelegramError as exc:
                self._on_error(exc)
                return True
            with self.sessionmaker().begin() as db:   # health for sign-in (FR-013)
                service.settings_row(db, lock=True).last_poll_ok_at = service.now()

            for update in updates:
                update_id = update["update_id"]
                try:
                    with self.sessionmaker().begin() as db:
                        handle_update(db, bot, update)
                        service.settings_row(db, lock=True).update_offset = update_id + 1
                except TelegramError as exc:
                    self._on_error(exc)
                    return True
                except Exception:
                    # Advance past a poison update; log the id only, never payloads.
                    log.exception("telegram update %s failed", update_id)
                    with self.sessionmaker().begin() as db:
                        service.settings_row(db, lock=True).update_offset = update_id + 1
        finally:
            bot.close()

        self._backoff = 1.0
        return True

    def _on_error(self, exc: TelegramError) -> None:
        if exc.code in ("invalid_credential", "webhook_conflict"):
            with self.sessionmaker().begin() as db:
                row = service.settings_row(db, lock=True)
                row.last_check_ok = False
                row.last_check = {"reason": exc.code}
            log.warning("telegram bot problem (%s); sign-in paused until checked", exc.code)
            self.stop.wait(60)
        else:
            log.warning("telegram poll failed (%s)", exc.code)
            self._sleep_backoff()

    def _sleep_backoff(self) -> None:
        self.stop.wait(self._backoff)
        self._backoff = min(self._backoff * 2, 60.0)
