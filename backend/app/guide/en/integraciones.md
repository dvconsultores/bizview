# Integrations

## What it is for

It shows the data loads of the active version: when they run, whether they ended well, and lets
you pause them, run them by hand or change their frequency.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Integrations](app:/admin/integraciones).
2. Each integration shows its status (**Active**, **Paused** or **Running**), the **Next run** and
   the **Last successful run**.
3. Actions: **Pause** / **Resume**, **Run now** (incremental load), **Full run** (reloads
   everything) and **Stop** a running run.
4. **Change frequency** opens the form: choose **Every 15 minutes**, **Every 30 minutes**,
   **Every hour**, **Daily** or **Custom** with a **Cron expression** (at most once every
   5 minutes). Optional: an **Allowed schedule** to start and a periodic **Full reload**.
5. **Use spec schedule** goes back to the frequency the spec states.

## Options

- **History** lists the runs: **Scheduled**, **Manual** or **Manual full**, with their result
  (**Succeeded**, **Failed**, **Skipped** or **Running**) and the path used: **COPY**,
  **COPY + Polars**, **rows** or **rows + Polars**.

## Common problems

- **Source disabled**: the integration does not run until its source is **Enabled** again.
- "No active integrations": apply a project or a workspace with integration specs.
