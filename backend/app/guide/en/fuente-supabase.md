# Supabase source

## What it is for

It reads data from a Supabase project through its REST API, without opening the database.

## Who can use it

Only the **Superuser**.

## How to

1. In [Open New source](app:/admin/fuentes/nueva) choose the Supabase **Source type**.
2. Type the project URL (one ending in `/rest/v1` is accepted too).
3. Paste a service key; a read-only key is recommended.
4. Press **Test connection** and then **Save**.

## Options

- BizView only reads (GET) from Supabase.
- For logic across several tables (joins, calculations), create a view in Supabase and read it
  as a table.

## Common problems

- Reconciliation (comparing totals with the origin) is not available for Supabase; only for
  PostgreSQL.
