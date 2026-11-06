# Sign in with Google

## What it is for

Signing in with your organization's Google account, without another password, and letting the
installation decide the role and the dashboards you come in with.

## Who can use it

Anyone whose Google address belongs to an allowed domain. The policy is configured with the
**Superuser** role, in Administration → Security → **Sign-in with Google**.

## How to

1. Open [Open the sign-in page](app:/ingresar).
2. Press **Continue with Google** and pick your account.
3. The first time, and when the installation has automatic sign-up on, BizView creates your user
   with the role and access the policy sets. If you already had an account, you come in with it.
4. If your account has two-step verification, type the 6-digit code.

## Options

- **Allowed domains**: the domains that may come in. Until you save the list it is the one the
  installation ships (GOOGLE_ALLOWED_DOMAINS); the first save turns it into configuration. If that
  variable carries something that is not a domain, the card says so and, until you save a list,
  nobody can sign in with Google.
- **Automatic sign-up**: with the switch on, an unknown account on an allowed domain is created on
  first sign-in. Pick the default role — never **Superuser** — and the default access: none, every
  public dashboard or a list of dashboards. The access applies to accounts with the **User** role; an
  administrator sees the whole catalogue through their role.
- **Role rules**: evaluated top to bottom, and the first match wins. Each rule looks at the domain
  or a list of addresses and decides the role and the access. The group condition arrives when the
  installation has a Workspace service account.
- **Linking by email**: an existing user is recognised by email and keeps its role. A rule only
  changes it when you turn on "apply rules to existing users too", and every change is audited.
- The button and these settings only exist when the installation has Google sign-in enabled.

## Common problems

- "Couldn't sign in with Google. Try again.": the message is always the same. The real reason — a
  domain that is not allowed, an account with no user, a deactivated account — is written to
  [Read the audit log](app:/admin/auditoria).
- The button is missing: the installation does not have Google sign-in configured.
- Changing the role of an account created automatically: do it in **Users**. Following sign-ins keep
  what the administrator set, unless the rules also apply to existing users.
- Unlinking a Google account: an **Administrator** deactivates the user or sets a password; from
  then on the account signs in with email and password.

## Related

- Sign in to BizView
- Security
- Users
