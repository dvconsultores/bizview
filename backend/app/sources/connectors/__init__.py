"""Origin connectors (feature 004); the kind list lives in `registry` (feature 061)."""
from app.config import Settings
from app.sources.connectors.base import TestResult
from app.sources.connectors.registry import KINDS

__all__ = ["KINDS", "test_source"]


def test_source(kind: str, settings: dict, secrets: dict, app: Settings) -> TestResult:
    from app.sources.connectors import registry

    return registry.test_source(kind, settings, secrets, app)
