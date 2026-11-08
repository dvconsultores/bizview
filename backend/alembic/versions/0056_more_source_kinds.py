"""Five more kinds of data source (feature 061).

A customer's ERP runs on MySQL or SQL Server, a small system exports a `.sqlite` file, a consultant
lands data in BigQuery and a business keeps prices in a Google Sheet. Until now the `data_source`
kind could only be PostgreSQL, Supabase, REST or SOAP, so none of those customers could be served.

The column keeps its shape and only the CHECK widens. The list of kinds the product shows comes from
`app/sources/connectors/registry.py`; this constraint mirrors it so a kind that is not in the code
cannot be stored. Downgrading refuses while any of the new kinds exists, exactly as 0010 did for
Supabase: dropping the constraint would otherwise leave rows the old CHECK forbids.

Revision ID: 0056_more_source_kinds
Revises: 0055_source_connection_limits
Create Date: 2026-11-08
"""
import sqlalchemy as sa

from alembic import op

revision = "0056_more_source_kinds"
down_revision = "0055_source_connection_limits"
branch_labels = None
depends_on = None

KIND_CHECK = "ck_data_source_kind"
#: The audit CHECK 0055 recreates (`ck_audit_event_ck_audit_event_kind`, double-prefixed by the
#: naming convention because 0055 named it explicitly). 0055 left two kinds out of its frozen list
#: — `starter_downloaded` and the three `mail_list_*` — so a database that ran it refuses the audit
#: event of a starter download and of a mailing list. This revision repairs it from the list the
#: code writes, which is the only source that cannot drift from it.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: Frozen copies: a database that already holds these breaks here if the list is shortened, so the
#: migration keeps its own list instead of reading `models.SOURCE_KINDS`.
KINDS_0055 = ("postgresql", "soap", "rest", "supabase")
KINDS_0056 = ("postgresql", "soap", "rest", "supabase", "sqlite", "mysql", "mssql", "bigquery",
              "sheets")


def _check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{kind}'" for kind in kinds) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source", _check(KINDS_0056))
    _repair_audit_kinds()


def _repair_audit_kinds() -> None:
    from app.models import AUDIT_KINDS

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _check(AUDIT_KINDS))


def downgrade() -> None:
    # Refuse rather than silently delete configured sources (and their encrypted secrets).
    count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM data_source WHERE kind <> ALL(:kinds)"),
        {"kinds": list(KINDS_0055)}).scalar()
    if count:
        raise RuntimeError(
            f"{count} fuente(s) de los tipos nuevos existen: elimínalas antes de bajar de 0056")
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source", _check(KINDS_0055))
    # The audit repair is not undone: the list it left is the one the code writes, and no kind
    # 0055 carried is missing from it.
