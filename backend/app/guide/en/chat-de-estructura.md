# Structure chat

## What it is for

It answers questions about what a source holds —tables, columns, types, keys, endpoints and response
shapes— and can draft the notes of `structure.md` or a paragraph for your `REQUEST.md`. It does not
read data: no rows, no business figures, no addresses.

## Who can use it

Only the **Superuser**, and only when the installation has an AI provider configured.

## How to

1. Open the source and go to the **Structure** tab (see A source's structure).
2. In the **Structure chat** panel, write the question and press **Ask**, or use Ctrl+Enter.
3. Read the answer: table and column names appear exactly as the source spells them.
4. To start over, press **Clear conversation**.

## Options

- An answer warns you when it names objects that do not exist in the source: do not use them in a
  spec.
- The counter shows the tokens spent today; the installation sets a daily limit per person and per
  source.
- When the provider fails, the message names the reason and links to [Open Artificial intelligence](app:/admin/ia).

## Common problems

- "The structure chat needs an AI provider": ask the **Superuser**; it is configured in
  [Open Artificial intelligence](app:/admin/ia), and the rest of the tab keeps working.
- "The structure chat does not read data": the question asked for rows or for an action; ask about
  the structure instead (which table or field holds that value).
- "You reached this chat's daily limit": come back tomorrow, or ask for a higher limit in
  [Open Artificial intelligence](app:/admin/ia).
