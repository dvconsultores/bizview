# Artificial intelligence

## What it is for

It shows whether AI is active, with which provider and model, and lets you test the connection.

## Who can use it

Only the **Superuser**. AI is optional.

## How to

1. Open [Open Artificial intelligence](app:/admin/ia).
2. Check the **Status** (**Enabled**, **Disabled** or **Incomplete configuration**), the
   **Provider**, the **Model**, the **API key** (**Configured** or **Not configured**) and the
   **Maximum time**.
3. Press **Test connection**. You see **Connection successful** with the response time or
   **Test failed** with the reason.

## Options

**How to enable it**: AI is configured in the installation's settings file and requires a
restart:

- Claude: `AI_PROVIDER=anthropic` and `AI_API_KEY`.
- Local model (data never leaves your network): `AI_PROVIDER=openai_compatible`, `AI_BASE_URL`
  and `AI_MODEL`.

Only aggregated figures are sent; never detailed records, passwords or personal data.

## Common problems

- **Test failed**: check the key, the local model address or the maximum time.
- **Incomplete configuration**: the screen lists the missing settings.
