#!/bin/sh
# Backend for the browser tests: DATABASE_URL_BI from .env, but a dedicated schema
# app_test_e2e that is rebuilt here and dropped by tests/e2e/teardown.ts. Never schema `public`.
set -e
cd "$(dirname "$0")/../../../backend"
export DB_SCHEMA=app_test_e2e BIZVIEW_TEST_HOOKS=1
export SUPER_USER_EMAIL=e2e-root@example.com SUPER_USER_PASSWORD=E2e-super-pass-1 COOKIE_SECURE=false \
       PRODUCT_NAME="Bizview AI Powered" ORGANIZATION_NAME="Cliente Demo" LOGO_URL= \
       SECURITY_PROFILE=private DATABASE_URL_ORIGIN= ADMIN_ALLOWED_NETWORKS= TIMEZONE=America/Caracas \
       AI_PROVIDER=none AI_API_KEY= AI_MODEL= AI_BASE_URL= AI_VISION=true \
       SMTP_HOST= SMTP_PORT= SMTP_SECURITY= SMTP_USER= SMTP_PASSWORD= SMTP_FROM= SMTP_FROM_NAME= \
       EMAIL_ALLOWED_DOMAINS= SHARE_LINKS_ENABLED=false \
       DIRECT_REPORTS_BI=true DIRECT_BI_ROLE=
# Feature 005: a generated workspace, applied and loaded once (tests.e2e_schema seed).
WORKSPACE_PATH="$(mktemp -d)/workspace"
export WORKSPACE_PATH
# Feature 020: BI projects in a fresh folder per run, never the repository's projects/.
PROJECTS_DIR="$(mktemp -d)/projects"
export PROJECTS_DIR
# Feature 024: chat image briefs in a throwaway folder, never the repository's attachments/.
ATTACHMENTS_DIR="$(mktemp -d)/attachments"
export ATTACHMENTS_DIR
# Feature 044: images cached from a URL column in a throwaway folder, never the repository's.
IMAGE_CACHE_DIR="$(mktemp -d)/image-cache"
export IMAGE_CACHE_DIR
uv run --quiet python -m tests.e2e_schema drop
uv run --quiet alembic upgrade head
uv run --quiet python -m app.cli bootstrap
uv run --quiet python -m tests.e2e_schema seed "$WORKSPACE_PATH"
exec uv run --quiet uvicorn app.main:app --port 8001
