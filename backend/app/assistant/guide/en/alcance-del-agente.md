# What the agent does and does not do

## What it is for

It explains the agent's limits, so you know what to ask and what to expect.

## Who can use it

Only the **Superuser**.

## How to

- It only handles reports, dashboards, integrations, ETL, data sources, the project's specs and the
  use of BizView. For other topics it answers with a fixed sentence and a few examples, without
  calling the AI.
- It changes files only inside a command (`/speckit-…`). In a message without a command it can
  look at sources and files and answer, and it proposes the right command with an **Insert**
  button.
- It reads the structure of sources (tables, columns, types) and aggregate figures, never rows or
  credentials.
- Text it reads from sources and files is data, never an order: if it finds instructions there, it
  mentions them to you but does not follow them.
- Columns with personal data are excluded unless you ask for them by name and confirm; the spec
  records it.
- It never applies a project: applying is always your action.

## Options

- Each conversation has a usage budget that grows by itself up to a maximum; the agent works on
  its own for several rounds and stops when done, out of budget or when you stop it.
