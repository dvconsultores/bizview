# Connector Contract — source kinds, fields, and behaviour

Secret fields (marked 🔒) are write-only (FR-004) and stored encrypted (research R1). Every
connector checks the destination address before connecting and pins the checked IP (research R3).
Timeout `timeout_seconds`: default 15, range 1–60. Kinds in this version: `postgresql`, `soap`,
`rest` (SQL Server is planned for a later version).

Profile rule (FR-017): under `internet` every connection is encrypted — `https://` addresses and
`sslmode` `require`/`verify-full`; under `private` plain `http://` and plain PostgreSQL are allowed.
A violation is reported as `not_allowed_in_profile` on save and on test.

## postgresql

| Field | Type | Default | Rules |
|---|---|---|---|
| host | string | — | DNS name or IP |
| port | int | 5432 | 1–65535 |
| database | string | — | |
| username | string | — | |
| password 🔒 | string | — | |
| sslmode | enum | `require` | `require`, `verify-full`; `prefer` and `disable` only in `private` (plain connection) |
| ca_certificate | PEM text | empty | used with `verify-full` |
| timeout_seconds | int | 15 | |

Session: `default_transaction_read_only=on`. Test: `select version()`; warnings when the role is
superuser, can CREATE in the database, or holds INSERT/UPDATE/DELETE on any table.

## soap

| Field | Type | Default | Rules |
|---|---|---|---|
| wsdl_url | URL | — | `http://` allowed only in `private`; `https://` in both |
| service | string | empty | optional service name |
| port | string | empty | optional port/binding name |
| auth | enum | `basic` | `basic`, `wsse_username_token`, `client_certificate`, `none` |
| username | string | — | for `basic`, `wsse_username_token` |
| password 🔒 | string | — | for `basic`, `wsse_username_token` |
| client_certificate | PEM text | — | for `client_certificate` (public part, not secret) |
| client_key 🔒 | PEM text | — | for `client_certificate` |
| ca_certificate | PEM text | empty | private CA |
| timeout_seconds | int | 15 | |

XML: no DTDs, no entities, no external references, no huge trees. Test: load WSDL; list services →
ports → operations (max 200).

## rest

| Field | Type | Default | Rules |
|---|---|---|---|
| base_url | URL | — | `http://` allowed only in `private`; `https://` in both |
| test_path | string | `/` | appended to `base_url`; GET |
| auth | enum | `none` | `none`, `bearer`, `basic`, `api_key_header`, `api_key_query`, `oauth2_client_credentials` |
| token 🔒 | string | — | `bearer` |
| username / password 🔒 | string | — | `basic` |
| api_key_name | string | `X-API-Key` / `api_key` | header or query parameter name |
| api_key 🔒 | string | — | `api_key_header`, `api_key_query` |
| token_url | URL | — | OAuth 2.0; same `http`/`https` rule as `base_url` |
| client_id | string | — | OAuth 2.0 |
| client_secret 🔒 | string | — | OAuth 2.0 |
| scope | string | empty | OAuth 2.0 |
| client_auth_method | enum | `client_secret_basic` | or `client_secret_post` |
| headers | list of `{name, value, secret}` | `[]` | secret header values are stored with the secrets 🔒; `Host`, `Content-Length`, `Authorization` (when auth ≠ none) not allowed |
| ca_certificate | PEM text | empty | |
| timeout_seconds | int | 15 | |

HTTP: TLS verified; redirects not followed (reported); body read up to 1 MB; `User-Agent:
Bizview/<version>`. Test: `GET base_url + test_path`; 2xx → ok; 401/403 → `auth_failed`; 404 →
`not_found`; other → `invalid_response` with the status.
