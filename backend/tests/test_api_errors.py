"""The API error envelope: a 500 is diagnosable (feature 028 polish, 2026-10-22).

Owner reported a button that only said "Ocurrió un error inesperado"; without a reference the
traceback in the server log could not be matched to the click staff saw. The body now carries one.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import errors


def _client() -> TestClient:
    app = FastAPI()
    errors.install(app)

    @app.get("/boom")
    def boom():                      # pragma: no cover - the handler is what is under test
        raise RuntimeError("secreto-interno")

    return TestClient(app, raise_server_exceptions=False)


def test_internal_error_carries_a_reference_and_no_internals():
    r = _client().get("/boom")
    assert r.status_code == 500
    error = r.json()["error"]
    assert error["code"] == "internal"
    assert error["message"].startswith("Ocurrió un error inesperado")
    reference = error["message"].split("referencia ")[1].split(")")[0]
    assert len(reference) == 12 and reference.isalnum()
    # Never the exception text: it may hold a host, a query or a credential.
    assert "secreto-interno" not in r.text and "RuntimeError" not in r.text
