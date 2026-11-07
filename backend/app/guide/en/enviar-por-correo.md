# Send by email

## What it is for

Email a dashboard with its PDF and, if you want, a link to see it online.

## Who can use it

Anybody with access to the dashboard, when the installation has email configured.
**Include link** is for administrators only.

## How to

1. Open the dashboard and press **Send by email**.
2. In **Recipients** pick installation users and **Mailing lists**; the counter says how many people
   the send reaches.
3. For single addresses write an **External email** and press **Add**, or paste several in
   **Paste a list** separated by comma, semicolon, space or newline. The `Name <address>` form works
   too.
4. Write the **Subject** (if left empty the dashboard name is used) and a **Message (optional)**.
5. Tick **Attach PDF of the current period and filters**.
6. Administrators: tick **Include link** and choose the **Link validity (days)**.
7. To reuse the addresses you wrote, write a name in **Save these recipients as a list**.
8. Press **Send**.

## Options

- **Sends** shows the status of every send: **Queued**, **Sending**, **Sent**, **Partially sent** or
  **Failed**, with each recipient's status.
- **Re-send the failed ones** sends only the addresses that failed, with the same subject, message
  and attachments.
- An invalid address is shown in red and stops the send: fix it or remove it.
- There is no recipient or hourly ceiling: mail goes out in batches, at the pace the installation's
  provider allows. The PDF cannot exceed 10 MB.
- If the installation paused email, the send stays **Queued** and goes out when it resumes.
- If the installation restricts typed addresses to administrators, a regular user keeps sending to
  users and to lists.

## Common problems

- «Email sending is not available in this installation.»: the **Superuser** must configure email.
- «Only these domains are allowed»: the installation restricts external addresses; use an address
  of those domains or a list whose members are allowed.

## Related

- Mailing lists
- Share with a link
- Export to PDF or CSV
- Scheduled sends
