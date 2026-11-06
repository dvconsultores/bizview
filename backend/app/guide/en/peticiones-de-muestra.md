# Sample requests

## What it is for

In a REST or Supabase source it saves the paths you want to document. BizView runs them with the
stored credential and shows the shape of the response: which keys it carries, of which type, which
one is the array of records and which fields are worth declaring. It never stores response values.

## Who can use it

Only the **Superuser**.

## How to

1. Open the source and go to the **Structure** tab.
2. In **Sample requests**, write the **Name**, the **Relative path** (for example
   `v1/cryptocurrency/listings/latest`) and the parameters as `key=value`, comma separated.
3. Press **Add request**.
4. Press **Run** on the request: you will see **Records**, **Suggested fields**, **Dates** and
   **Pagination**.
5. The same information travels in the structure download.

## Options

- The path is always relative to the source's address: full URLs are refused.
- Only GET requests are run, so a source credential cannot write.
- **Remove request** deletes it from the source.

## Common problems

- "The path must be relative to the source's base URL": drop the `https://…` part and the leading
  slash.
- "The source responded with HTTP 403": the credential has no access to that path.
- "The response is not JSON": the path returns another format; document the structure by hand in
  the notes.

## Related

- A source's structure
- Integrations
- ETL and transformations
