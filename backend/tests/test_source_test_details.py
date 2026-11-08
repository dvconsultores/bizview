"""Probar conexión reports the origin's own ceiling and how full it is (feature 060).

The "origin" is the test database itself, read through the same connector a source uses.
"""
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.sources.connectors import postgresql


def settings_of_database() -> dict:
    url = make_url(get_settings().database_url_bi)
    return {"host": url.host, "port": url.port or 5432, "database": url.database,
            "username": url.username, "sslmode": "prefer", "timeout_seconds": 15}


def secrets_of_database() -> dict:
    return {"password": make_url(get_settings().database_url_bi).password}


def test_the_test_reports_the_ceiling_and_the_clients():
    result = postgresql.test(settings_of_database(), secrets_of_database(), get_settings())
    assert result.ok, result.message
    details = result.details
    assert details["clients_visible"] is True
    assert details["max_connections"] >= 10
    assert details["clients"] >= 1
    # The keys the UI reads; a missing one would silently hide the numbers.
    assert {"max_connections", "clients", "clients_visible"} <= details.keys()


def test_a_role_without_permission_still_reports_a_healthy_connection(monkeypatch):
    """`pg_stat_activity` unreadable is a normal case, never a failed test."""
    import psycopg

    original = psycopg.Connection.execute

    def refuse(self, query, *args, **kwargs):
        if "pg_stat_activity" in str(query):
            raise psycopg.errors.InsufficientPrivilege("permission denied for relation pg_stat_activity")
        return original(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Connection, "execute", refuse)
    result = postgresql.test(settings_of_database(), secrets_of_database(), get_settings())
    assert result.ok is True
    assert result.details["clients_visible"] is False
    assert "max_connections" not in result.details


def test_a_refused_slot_is_its_own_code():
    import psycopg

    class Busy(psycopg.OperationalError):
        def __init__(self, message):
            super().__init__(message)
            self.sqlstate = "53300"

    import app.sources.connectors.postgresql as connector

    class Client:
        @staticmethod
        def connect(**_kwargs):
            raise Busy("FATAL: sorry, too many clients already")

    original = connector.psycopg.connect
    connector.psycopg.connect = Client.connect
    try:
        result = connector.test(settings_of_database(), secrets_of_database(), get_settings())
    finally:
        connector.psycopg.connect = original

    assert result.ok is False
    assert result.code == "busy"
    assert result.details["sqlstate"] == "53300"
    assert "conexiones" in result.message or "slots" in result.message
