# Feature Specification: Sales Dashboard for Customers

## Overview

A mobile-first web dashboard that lets customers read their sales data.
The system has four components that run in Docker:

1. **Origin database** — an existing external system. Read-only.
2. **Integration worker** — a Python process that reads origin data via
   custom queries and writes transformed models into the dashboard's
   PostgreSQL schema.
3. **Backend** — FastAPI application that serves the transformed models
   through a JSON API, and generates PDF reports via ReportLab.
4. **Frontend** — React mobile-first SPA that consumes the API.

## Project Structure

> The original scaffold was truncated at this heading. This section is
> derived from constitution §2.4 (Separated Concerns by Folder).

- `backend/` — FastAPI application, models, ETL orchestration, API routes.
- `integration/` — Worker process that reads origin data and writes to the
  optimized models. Runs on its own schedule.
- `frontend/` — React mobile-first application.
- `custom_queries/` — Versioned SQL queries against the origin database.
- `docker-compose.yml` — backend, worker, frontend, postgres.
