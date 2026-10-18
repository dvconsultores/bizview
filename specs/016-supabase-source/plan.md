# Implementation Plan: Supabase data source

- `app/sources/schemas.py`: `SUPABASE` fields (`url`, `service_key`, timeout); `url` in the
  destination (SSRF) checks.
- `app/sources/connectors/supabase.py`: `api_base`, `rest_settings`, `rest_secrets`, `test`
  (delegates to the REST connector).
- `app/sources/describe.py`: `supabase()` + `openapi_tables()`; REST JSON fetch shared.
- `app/engine/extract.py` `supabase_rows`; `app/engine/runner.py` dispatch.
- `app/models.py` `SOURCE_KINDS`; migration `0010_supabase_source` (check constraint).
- Assistant system prompt: request-file format for Supabase/REST sources.
- Frontend: `SourceKind` + icon (form fields come from `/api/sources/types`).
- Tests: `tests/test_supabase_source.py`, migration test.
