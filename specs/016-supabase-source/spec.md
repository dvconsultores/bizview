# Feature Specification: Supabase data source

**Feature Branch**: `016-supabase-source`
**Created**: 2026-10-03
**Status**: Implemented
**Input**: Owner, 2026-10-03: "create one dedicated for supabase it uses SUPABASE_URL and
SUPABASE_SERVICE_KEY".

## User Scenarios & Testing

### User Story 1 - Connect a Supabase project (P1)
The super user adds a source of type "Supabase" with the project URL (SUPABASE_URL) and the
service key (SUPABASE_SERVICE_KEY), tests it, and integrations read its tables and views.

**Acceptance Scenarios**
1. **Given** Fuentes de datos → Nueva fuente, **When** "Supabase" is chosen, **Then** the form asks
   only for the project URL and the service key (plus the usual time limit).
2. **Given** a saved Supabase source, **When** "Probar conexión" is pressed, **Then** BizView calls
   `<url>/rest/v1/` with the key in the `apikey` header and as Bearer token and reports the result.
3. **Given** the assistant or an access token, **When** the source is described, **Then** tables
   and views are listed with column names, types, nullability and primary keys only.
4. **Given** an integration whose dataset uses a request file, **When** it runs, **Then** rows are
   read with GET requests, paginated, within the incremental window.

### Edge Cases
- The API address (`…/rest/v1`) pasted instead of the project URL works the same.
- The service key bypasses Supabase row-level security: BizView only issues GET requests; the
  form recommends a key limited to reading where possible.
- Reconciliation checks need SQL and stay PostgreSQL-only.

## Requirements
- **FR-001**: New source kind `supabase` with settings `url` and secret `service_key` (encrypted,
  write-only like every source secret).
- **FR-002**: Test, describe and extraction reuse the REST connector (SSRF guard, HTTPS rule of
  the security profile, response limits) with both Supabase headers added automatically.
- **FR-003**: Describe without a path returns tables/columns from the API's OpenAPI description,
  without defaults, comments or examples.
- **FR-004**: Product schema change through Alembic (`0010_supabase_source`); downgrade refuses
  while Supabase sources exist.
