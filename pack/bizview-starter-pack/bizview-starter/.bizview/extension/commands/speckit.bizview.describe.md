---
description: "Describe a data source (structure only) to write an integration spec"
---

# Describe a data source

Run `bizview describe "$ARGUMENTS"` (the environment must have `BIZVIEW_URL` and a personal token
in `BIZVIEW_TOKEN`, created by the super user in *Administración → Tokens*). The output lists
schemas, tables, columns, types and estimated row counts (or REST/SOAP operations and shapes). It
never contains data values or credentials. Use it to write the integration spec's origin notes and
the dataset queries. Do not paste any business data into specs or prompts.
