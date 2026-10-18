# Users

## What it is for

Create people's accounts, decide which dashboards each one sees and reset passwords.

## Who can use it

An **Administrator** manages **User** accounts. Only the **Superuser** manages administrators.

## How to

1. Open [Open Users](app:/admin/usuarios). Search with **Search by name or email** or filter by
   **Role** and **Status**.
2. To create an account, press **New user** ([Open New user](app:/admin/usuarios/nuevo)): type the
   name, email and role, press **Generate** for the **Temporary password** and then
   **Create user**. Give the temporary password to the person: it is shown once and they must
   change it when signing in.
3. Open a user to see their **Details** and their **Dashboard access**: tick the dashboards they
   can see and save.

## Options

- **Deactivate user**: they can no longer sign in and their open sessions are closed.
  **Reactivate user** brings them back.
- **Reset password**: closes their sessions and gives them a temporary password.
- **Reset two-factor**: the person sets up two-step verification again.
- **Remove Telegram link**: they cannot sign in with Telegram until they link it again.

## Common problems

- The user cannot be modified: they are an **Administrator** or the **Superuser**; only the
  **Superuser** changes them.
- Your own details are changed from your profile, not here.
