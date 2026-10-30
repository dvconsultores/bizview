# Data sources

## What it is for

A source is a system BizView reads data from: a PostgreSQL database, a SOAP or REST service, or a
Supabase project. Credentials are stored encrypted and never shown.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Data sources](app:/admin/fuentes) and press **New source**
   ([Open New source](app:/admin/fuentes/nueva)).
2. Choose the **Source type** (it cannot be changed later) and type the **Name**.
3. Fill in the **Connection**: address, database or service, encryption mode, authentication
   type, headers and credentials.
4. Press **Test connection**: you see **Connection successful** with the response time, or the
   reason for the error.
5. Press **Save**.

## Options

- Statuses in the list: **Untested**, **Connected**, **Error**, **Disabled** and
  **Imported: review**.
- **Enabled**: unticking it stops the integrations of that source.
- **Delete source** removes the source and its encrypted credentials.
- On PostgreSQL, **Allow direct reports** lets a report read the source live (see Direct
  reports).
- Credentials are write-only: to change them use **Replace**.

## Common problems

- "Address not allowed (local, internal or metadata)": BizView does not connect to internal
  addresses of its own server.
- With the internet profile only encrypted connections (HTTPS/TLS) are allowed.
