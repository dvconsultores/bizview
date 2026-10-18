# Privacy and AI

## What it is for

It explains what artificial intelligence does in BizView and which data it never receives.

## Who can use it

Anyone with an account. AI is optional: the **Superuser** turns it on and, without it,
everything else works the same.

## How to

- **AI summary** in a report: the AI receives only the totals the report spec defines, never
  records.
- The **Superuser**'s assistant sees the structure of sources (tables, columns, types) and
  aggregate figures, never rows or credentials.
- Columns that look like personal data (emails, phones, IDs) are excluded unless the
  **Superuser** asks for them by name and confirms.
- The installation can use Claude or a local model; with a local model nothing leaves the
  installation.

## Common problems

- If you see neither **AI summary** nor the assistant, AI is not configured in this
  installation.
