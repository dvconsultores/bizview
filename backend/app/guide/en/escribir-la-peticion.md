# Write the request

## What it is for

`REQUEST.md` is the brief: which question the dashboard answers, who reads it, which figures they
want, with which cuts and in which style. BizView never imports it; your AI reads it. Five minutes
here save a week of corrections.

## Who can use it

Only the **Superuser**, in the pack they downloaded.

## How to

1. Open the pack's `REQUEST.md` with any text editor.
2. Write the question in one sentence, in the business's own words.
3. Say who reads it and what they decide with what they see.
4. List the figures and their format: currency, integer or percentage.
5. Add the cuts, the default period and the ones they want to pick from.
6. Describe the style: what goes on top, which chart, whether it needs a PDF or images.
7. Say what is out of scope and whether any personal data appears.

When a source was chosen there is no need to describe its tables: they are in
`sources/<source>/structure.md`.

## Options

- It can be written in Spanish or in English; you choose the language of the labels.
- If you do not know which figures you want, ask first for one business sentence and one table; the
  rest is refined later, on a dashboard that already works.

## Common problems

- A request that mixes three questions produces a dashboard that answers none: one request, one
  dashboard, and the others in later projects.
- Asking for "all the data" without column names: without a structure your AI will invent, and the
  import will say so.

## Related

- Download the starter pack
- Hand it to your AI
- Spec kinds
