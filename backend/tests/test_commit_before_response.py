"""Regression: a request's transaction commits before its response is sent.

FastAPI runs the exit code of `yield` dependencies after the response by default. With a remote
database the browser then received the new session cookie before the session row was committed,
and its next request got 401 (found by the browser suite against the external database).
"""
import asyncio
import json

from app.main import app
from tests.conftest import PASSWORD, sql


def test_login_session_is_committed_when_the_response_starts(user):
    body = json.dumps({"email": user.email, "password": PASSWORD}).encode()
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": "/api/auth/login", "raw_path": b"/api/auth/login",
        "query_string": b"", "root_path": "", "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                    (b"x-requested-with", b"fetch"),
                    (b"content-length", str(len(body)).encode())],
    }
    seen: dict = {}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            seen["status"] = message["status"]
            # Another connection must already see the session the cookie refers to.
            seen["sessions"] = sql("SELECT count(*) FROM user_session")[0][0]

    asyncio.run(app(scope, receive, send))
    assert seen == {"status": 200, "sessions": 1}
