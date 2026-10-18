"""Verify TCP liveness parameters are applied to BI database connections."""
from app.config import Settings
from app.db import TCP_LIVENESS, get_engine
from app.sources.connectors.postgresql import connect_kwargs


def test_engine_connection_reports_liveness_parameters():
    raw = get_engine().raw_connection()
    try:
        params = raw.driver_connection.info.get_parameters()
        for key, value in TCP_LIVENESS.items():
            assert params[key] == str(value)
    finally:
        raw.close()


def test_connect_kwargs_contains_liveness_parameters():
    app = Settings(database_url_bi="postgresql://x@localhost/x", security_profile="private")
    kwargs = connect_kwargs(
        settings={"host": "203.0.113.9", "port": 5432, "database": "erp", "username": "bi_ro"},
        secrets={"password": "pw"},
        app=app,
        ca_path=None,
    )
    for key, value in TCP_LIVENESS.items():
        assert kwargs[key] == value
    assert kwargs["hostaddr"] == "203.0.113.9"
