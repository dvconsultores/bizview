# Generate structure with AI

## What it is for

It reads a source, understands what it holds and saves the structure pack: the tables or
endpoints with their fields, types, keys, load date, relations, personal data and the notes that say
what one row is. That pack is what you hand to the AI that builds the dashboard outside BizView. You
type nothing: you press one button.

## Who can use it

Only the **Superuser**, and it needs an AI provider configured in Administration → AI.

## How to

1. Open the source and go to the **Structure** tab (see A source's structure).
2. Review **Sample requests**: those are the endpoints the generation reads.
3. Press **Generate structure with AI** and wait: the progress line says which step it is on (scan,
   AI, verification).
4. Read the result: every table with its "what one row is", its key, its date and its fields; below,
   the relations, the suggested metrics and what the check dropped.
5. Press **Download structure (.md)** or the JSON one to take the pack with you.

## Options

- **Refresh** reads the source again without AI; what was generated stays until you generate again.
- The changed summary appears after a generation and names the tables and fields that came in or went
  out against the previous pack.
- **Dropped by the check** lists what the model mentioned and the source does not have: it is not in
  the pack and must not be used in a spec.
- **Download the scan (.md)** gives the raw reading of the source, without AI.
- **Cancel** stops waiting; if the run finishes anyway, the pack is saved.

## Common problems

- The button is disabled: the AI provider is missing, or the run ceiling is zero
  (Administration → AI).
- "The model's answer did not form a valid pack": try again; the scan is still available and the
  previous pack was not lost.
- A SOAP source does not generate: its structure is the WSDL operation, there are no fields to infer.
