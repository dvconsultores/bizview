"""Guard for destructive test setup. Tests run on DATABASE_URL_BI but only inside a temporary
schema named app_test_*, which they create and drop. The real tables in `public` are never
written."""
import re

TEST_SCHEMA_RE = re.compile(r"app_test_[a-z0-9_]{1,40}")


def assert_test_schema(schema: str | None) -> str:
    if not schema or not TEST_SCHEMA_RE.fullmatch(schema):
        raise SystemExit(f"test schema {schema!r} must match app_test_*; refusing to run tests")
    return schema
