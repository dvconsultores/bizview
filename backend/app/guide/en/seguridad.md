# Security

## What it is for

It shows the installation's security profile, which controls are active and what needs
attention.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Security](app:/admin/seguridad).
2. At the top you see the profile: **Private profile** (private network: HTTP is allowed and
   two-factor is optional) or **Internet profile** (HTTPS required everywhere and two-factor for
   administrators). It can be **automatic** or **configured**.
3. Check the list of controls: each one says **Correct** or **Needs attention**.

## Options

- The profile is changed in the installation's settings file (`SECURITY_PROFILE`) and requires a
  restart.
- **Direct reads (24 h)** counts direct report queries per source.
- The **Sign in with Telegram** card sets up the Telegram bot.
- If a notice about `DATABASE_URL_ORIGIN` appears, that variable is no longer used: remove it from
  the settings file after checking the imported source.

## Common problems

- A control in **Needs attention** explains what is missing; fix it in the installation. BizView
  offers no way to turn off password confirmation or required two-factor.
