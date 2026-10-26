"""Pairing stored tool results with the assistant turn that asked for them (feature 036).

One implementation, three callers: the Alembic migration (every conversation, once), the
"Reparar conversación" action (one conversation, on demand) and the tests.

`assistant_message_id` is what makes a conversation replayable: the builder pairs by call id when
the column is empty, but the column is the durable answer, so a repaired conversation stays repaired
even if a call id were reused. A row that cannot be paired (`orphan`) is transcript only — a preview
notice, or a result whose `tool_use` was never stored — and is never sent to a provider.

The SQL is set-based on purpose: the migration runs over every conversation of an installation.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

log = logging.getLogger("app.assistant.repair")

# The call a tool row answers, when the row predates the column.
FILL_CALL_ID = """
UPDATE assistant_message AS t
   SET call_id = t.tool_payload ->> 'call_id'
 WHERE t.role = 'tool'
   AND t.call_id IS NULL
   AND t.tool_payload ? 'call_id'
   {scope}
"""


# The assistant turn whose `calls` contains that id, earlier in the same conversation.
PAIR = """
UPDATE assistant_message AS t
   SET assistant_message_id = (
        SELECT a.id
          FROM assistant_message AS a
         WHERE a.session_id = t.session_id
           AND a.role = 'assistant'
           AND a.id < t.id
           AND a.tool_payload -> 'calls'
               @> jsonb_build_array(jsonb_build_object('id', t.call_id))
         ORDER BY a.id DESC
         LIMIT 1)
 WHERE t.role = 'tool'
   AND t.call_id IS NOT NULL
   AND t.assistant_message_id IS NULL
   {scope}
"""


# Everything left over cannot be replayed.
FLAG = """
UPDATE assistant_message AS t
   SET orphan = true
 WHERE t.role = 'tool'
   AND t.orphan = false
   AND (t.assistant_message_id IS NULL
        OR NOT EXISTS (
            SELECT 1
              FROM assistant_message AS a
             WHERE a.id = t.assistant_message_id
               AND a.tool_payload -> 'calls'
                   @> jsonb_build_array(jsonb_build_object('id', t.call_id))))
   {scope}
"""


def repair(db, session_id: int | None = None) -> dict[str, int]:
    """Pair and flag; answers what changed. `session_id=None` repairs the whole installation."""
    scope = "" if session_id is None else "AND t.session_id = :sid"
    params = {} if session_id is None else {"sid": session_id}
    filled = db.execute(text(FILL_CALL_ID.format(scope=scope)), params).rowcount or 0
    paired = db.execute(text(PAIR.format(scope=scope)), params).rowcount or 0
    flagged = db.execute(text(FLAG.format(scope=scope)), params).rowcount or 0
    return {"call_ids": filled, "paired": paired, "orphans": flagged}


def repair_everything(db) -> dict[int, int]:
    """The migration's pass: repair all, then report the orphan count per conversation."""
    totals = repair(db)
    log.info("assistant history repaired: %s", totals)
    rows = db.execute(text(
        "SELECT session_id, count(*) FROM assistant_message "
        "WHERE role = 'tool' AND orphan GROUP BY session_id ORDER BY 1"
    )).all()
    by_session = {session: int(count) for session, count in rows}
    for session, count in by_session.items():
        log.info("assistant session %s keeps %s orphan tool result(s)", session, count)
    return by_session
