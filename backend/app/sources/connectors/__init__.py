"""Origin connectors (feature 004). `test_source(kind, settings, secrets, app)` → TestResult."""
from app.config import Settings
from app.sources.connectors.base import TestResult, timed


def test_source(kind: str, settings: dict, secrets: dict, app: Settings) -> TestResult:
    if kind == "postgresql":
        from app.sources.connectors import postgresql as mod
    elif kind == "rest":
        from app.sources.connectors import rest as mod
    elif kind == "soap":
        from app.sources.connectors import soap as mod
    elif kind == "supabase":
        from app.sources.connectors import supabase as mod
    else:
        return TestResult(False, "error", "Tipo de fuente no soportado.")
    return timed(lambda: mod.test(settings, secrets, app))
