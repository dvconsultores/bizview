# Fixing an email send

## What it is for

Understanding why a send did not arrive, who received it, and how to re-send only what failed
without typing the recipients again.

## Who can use it

Anyone with access to the dashboard sees the sends they made; an **Administrator** sees everybody's.
Only whoever sent it or an administrator can **Re-send the failed ones**.

## How to

1. Open the dashboard, press the ⋯ menu and choose **Sends**.
2. Each row says the date, who sent it, how many recipients and of which kind (users, lists,
   addresses). Addresses are shown masked: `a***@cliente.com`.
3. Expand a send to see each person's status: **Sent**, **Queued**, **Failed** or **Skipped**, with
   the reason when it failed.
4. If something failed, press **Re-send the failed ones**: a new send is queued with only those
   people, the same subject, message and period.

## Options

- A big send is delivered in batches; the installation decides how many recipients per message and
  how fast, so 1,500 people may take a few minutes to all read **Sent**.
- If the installation has sending paused, sends keep being accepted and stay **Queued** until it
  resumes.
- **Skipped** is not **Failed**: the dashboard is no longer available or the person lost access, and
  re-sending does not fix it.

## Common problems

- "The mail server refused the recipient": that address does not exist or its mailbox is full. Fix
  it in the list and send again.
- "The mail server refused the sender address": the installation needs a sender its provider
  authorises; tell the **Superuser**.
- "Nothing to send": tick **Attach PDF** or **Include link**.
- "The PDF exceeds 10 MB and no link was requested": tick **Include link** to send only the link.

## Related

- Send by email
- Mailing lists
- Scheduled sends
