# A source's structure

## What it is for

It shows what a connection holds so you can write its spec: schemas, tables and views with their
columns, types, keys, approximate row counts and date ranges; for a REST or Supabase source, the
sample requests with the shape of their response; for SOAP, its operations. It never shows row
values.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Data sources](app:/admin/fuentes) and enter the source.
2. Press the **Structure** tab: BizView reads the source (structure only) and shows it.
3. Use **Search table or column** to find an object in a large catalogue.
4. Press **Download structure (.md)** or **Download structure (.json)** to take it to the authoring
   pack: they are the `sources/<name>/structure.md` and `structure.json` files.
5. Write what is missing in **Notes** and press **Save notes**: that text travels in the
   "Observaciones" section of the download.
6. For a source that changed, press **Refresh** to read it again.

## Options

- The **personal** chip marks the columns that look like personal data (e-mail, name, phone,
  document, chat identifiers). Press it to change the flag: the choice is stored and kept in the
  download.
- The **Dates** range comes from the minimum and maximum of up to three date columns per table.
- When the catalogue is very large the structure is truncated and the download says so in its notes.

## Common problems

- "The source responded with HTTP…" or a network error: check the connection in the **Connection**
  tab and press **Test connection**.
- A table you expected is missing: the credential may not have read permission on it.
