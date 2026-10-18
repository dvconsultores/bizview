# Access tokens

## What it is for

A token lets the `bizview describe` command line read the structure of sources (tables and
columns, never data) while you write specs on your machine.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Access tokens](app:/admin/tokens).
2. Press **New token**, type a **Name** (for example, your laptop) and choose
   **Expires in (days)**.
3. Press **Create token** and copy it: it will not be shown again.
4. On your machine, use it with `bizview describe`.

## Options

- The list shows when each token expires and when it was last used.
- Revoke a token you no longer use; revoked or expired tokens stop working at once.
- Creating and revoking tokens is recorded in the audit.
