"""`bizview describe`: environment, auth failures, output."""
import httpx
import pytest

from bizview_cli import describe as mod
from bizview_cli.__main__ import main


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("BIZVIEW_URL", "https://bi.example.com/")
    monkeypatch.setenv("BIZVIEW_TOKEN", "bzv_x")


def test_needs_url_and_token(monkeypatch, capsys):
    monkeypatch.delenv("BIZVIEW_URL", raising=False)
    monkeypatch.delenv("BIZVIEW_TOKEN", raising=False)
    assert main(["describe", "Origen"]) == 2


def test_prints_structure_as_yaml(env, monkeypatch, capsys):
    seen = {}

    def fake_get(url, params=None, headers=None, **kw):
        seen.update(url=url, params=params, headers=headers)
        return FakeResponse(200, {"kind": "postgresql", "tables": [{"name": "ventas"}]})

    monkeypatch.setattr(mod.httpx, "get", fake_get)
    assert main(["describe", "Origen ERP", "--path", "/x"]) == 0
    assert seen["url"] == "https://bi.example.com/api/sources/Origen%20ERP/describe"
    assert seen["headers"]["Authorization"] == "Bearer bzv_x" and seen["params"] == {"path": "/x"}
    assert "kind: postgresql" in capsys.readouterr().out


@pytest.mark.parametrize("status,body", [(401, {}), (502, {"error": {"message": "caída"}})])
def test_errors_exit_3(env, monkeypatch, status, body):
    monkeypatch.setattr(mod.httpx, "get", lambda *a, **k: FakeResponse(status, body))
    assert main(["describe", "Origen"]) == 3


def test_network_error_exit_3(env, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no")
    monkeypatch.setattr(mod.httpx, "get", boom)
    assert main(["describe", "Origen"]) == 3
