# The source has no free connection slots

## What it is for

What to do when an integration ends amber with "The source has no free connection slots". It is not a
BizView defect and not a data problem: the origin server had no free connections left and refused
ours.

## Who can use it

The **Superuser** and whoever administers the origin database.

## How to

1. It is the origin's limit, not BizView's. Another system owns that database (the ERP, for example)
   and its own clients took every slot. BizView opens one connection per source (or as many as
   Simultaneous connections says) and closes it when it is done.
2. On the origin, look at the ceiling and at who holds it:

   ```sql
   SHOW max_connections;
   SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY 1, 2;
   ```

   BizView sessions show up as `bizview-engine:<integration>`.
3. Pick one of the four real remedies:
   - put a PgBouncer (transaction pooling) in front of the origin;
   - ask the ERP vendor to raise `max_connections`;
   - point BizView at a read replica;
   - move the schedule to a quiet hour or widen the window instead of running every hour (or use
     `materialize: daily` on the reports).
4. While you sort it out there is nothing to repair: dashboards keep showing the last loaded data,
   with its "Data updated" time. The next run tries again.

## Options

- An amber run carries the number of attempts and the wait (4 attempts, 7 min) and this link.
  BizView waits and retries on its own before giving up.
- If the origin was full three times in a row, the superuser gets a single notice, not one per
  attempt.
- When the integration accumulates several such runs in the day, its page suggests the hour the
  origin was quietest.
- **Test connection**, on the source, shows the origin's maximum connections and how many
  clients it has now, when BizView's user may read the session list; otherwise it says "No
  permission to see it".

## Common problems

- "No permission to see it": the source's user cannot read `pg_stat_activity`. The connection works;
  the numbers are for whoever administers the origin.
- The error names BizView's host, not the origin's: then it is something else — the product's own
  database ran out of connections. Raise `DB_POOL_SIZE` or `DB_POOL_OVERFLOW` and check
  `docker compose logs backend`.
- "Could not connect to the source" in red: that is not this case. The network or the server is not
  answering, and retrying will not fix it.

## Related

- Integrations
- Scheduled deliveries
- Data sources
