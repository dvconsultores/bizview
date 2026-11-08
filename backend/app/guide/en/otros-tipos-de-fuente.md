# MySQL, SQL Server, SQLite, BigQuery and Google Sheets

## What it is for

Besides PostgreSQL, a REST and a SOAP service, BizView reads five more kinds of source. All of them
are registered the same way —**New source**, **Test connection**, **Save**— and all of them are
read-only: the source belongs to the system that uses it, and BizView never writes to it.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Data sources](app:/admin/fuentes) and press **New source**.
2. Choose the type and write the **Name**.
3. Fill in the connection and press **Test connection**: you will see **Connection successful** or
   the reason it failed. If the credential can write, the card says so as a warning.
4. Press **Save** and then look at the **Structure** tab.

## Options


| Kind | Read-only credential | Note |
|---|---|---|
| MySQL / MariaDB | a user with `GRANT SELECT` | port 3306 |
| SQL Server | a login with `db_datareader` | port 1433; Azure AD is not supported |
| SQLite | none: it is a file | only the files of the installation's folder are listed |
| Google BigQuery | a service account with BigQuery Data Viewer and Job User | paste its JSON; there is a bytes ceiling per query |
| Google Sheets | a service account, with the sheet shared with its address | each worksheet is a table |



- Simultaneous connections: how many connections BizView may open at once on that source.
- **Structure**: shows the tables, the columns and their types; it is saved into a pack the external
  AI reads to write the integration.
- In Sheets, each worksheet is a table and the first row is the header.
- In BigQuery the query is dry-run first: if it would scan more bytes than the ceiling it does not
  run, and the run says how much it would have read.

## Common problems

- **Not available in this installation**: that kind's driver or the files folder is missing.
  Whoever administers the server fixes it.
- **The source has no free connection slots**: the origin is full; the load ends amber and retries.
  Lower the source's simultaneous connections or move the schedule.
- Share the sheet with this address: the message carries the service account's exact address;
  share the sheet with read access.
