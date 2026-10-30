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

When the provider fails, the chat and this screen show a short code with its meaning and the text
the provider returned. Every code has exactly one way out:

- `not_configured` — **The AI is not configured.** Fill in `AI_PROVIDER`, `AI_API_KEY` and
  `AI_MODEL` and restart the installation.
- `no_credit` — **The AI provider account has no balance.** Top up the provider account. While it
  stays like this the agent does not call the provider: every attempt is refused instantly and
  burns no tokens. The **Blocked until it is fixed** band says so on this screen.
- `bad_key` — **The API key is not valid or is not allowed to use this model.** Check `AI_API_KEY`
  (no stray spaces or quotes) and that the key belongs to the same provider as `AI_BASE_URL`.
- `model_not_found` — **The configured model does not exist or is not available.** Compare
  `AI_MODEL` with **Models the provider reports** below: if the name is not there, fix `AI_MODEL`.
- `rate_limited` — **The provider rate-limited the requests.** Wait and press **Retry**: the agent
  honours the wait the provider asks for (up to 60 s) and retries once only.
- `context_too_long` — **The conversation exceeded the model's maximum context.** Start a new
  session or sum up the brief in fewer words.
- `provider_down` — **The AI provider does not answer or returns a server error.** Retry in a few
  minutes; if it stays the same, check the provider's status page.
- `invalid_tool_call` — **The model returned a malformed tool call.** Retry; if it repeats with the
  same model, change `AI_MODEL`.
- `refused` — **The provider refused the request.** Rephrase the message; if it insists, change
  model.
- `provider_error` — **The AI provider returned an error.** The detail is in the server log
  (below).

If the agent stops by itself, the summary names the reason (`blocked:ai_<code>`): it is not a
network glitch, it is the provider. A "continue" or "fix it" message during a block is refused the
same way, without calling the provider, until the code is fixed.

**Test failed** also shows when **Incomplete configuration** lists missing settings. The test does
two things: a one-token answer and a tool call; **Tool call** tells you which of the two failed.

### Where the detail is

**Technical details**, under every error and under the test, shows when it happened, the model and a
reference to search for. The full text is in the backend log, not the proxy's (Caddy):

```sh
docker logs --tail 200 bizview-backend | grep -i "AI"
```

### Fixes that do not need the AI

If the problem is in the project and not in the provider (a missing `joins`, a missing `date`, an
unknown view type), the **Problems** panel offers **Apply fix** on that warning, and the header
button applies every fix at once. It works in any mode, even with the AI down: it does not call the
provider, it edits the draft, validates again and leaves the change in the audit log.
