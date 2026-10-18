# Distributions

## What it is for

A distribution spec defines how a project's report is shared: scheduled email sends and the
shared-link policy. It is applied together with the project.

## Who can use it

Only the **Superuser** writes it; sends reach the users of the chosen roles.

## How to

1. Write the spec with `/speckit-specify` (for example "weekly send of the sales report to the
   administrators") and follow the method up to `/speckit-implement`.
2. The agent writes `distributions/<id>.yaml`:
   - `report`: the id of the report that is sent.
   - `subscriptions`: each send with `frequency` (`daily`, `weekly` or `monthly`), `hour`,
     `weekday` or `monthday`, `period`, `recipients` by role (`admin` or `user`), `attach_pdf` and
     `link_days`.
   - `share`: `allowed` (whether shared links of the report are allowed) and `max_days`.
3. Apply the project.

## Options

- Recipients are always roles, never email addresses.
- On the dashboard screen, a project send shows as **Managed by project** …: there it can only be
  paused or resumed.
- Sends made by hand in **Scheduled sends** do not depend on any project.
