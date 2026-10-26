# Contract: provider error codes

One closed vocabulary, shared by the backend, the API, the interface and `/api/health`.

| Code | HTTP / cause | Transient | Action (`action`) |
|---|---|---|---|
| `no_credit` | 402 | no | `admin_ai` |
| `bad_key` | 401, 403 | no | `admin_ai` |
| `model_not_found` | 400/404 whose body names the model | no | `admin_ai` |
| `not_configured` | AI off or incomplete | no | `admin_ai` |
| `rate_limited` | 429 (`retry_after` when sent) | yes | `retry` |
| `provider_down` | 5xx, timeout, connection error | yes | `retry` |
| `context_too_long` | 400 naming length/tokens | no | — |
| `invalid_tool_call` | malformed tool JSON after one repair round | no | — |
| `refused` | provider content filter | no | — |
| `provider_error` | anything else | no | — |

**Guarantees**

1. Every code has a Spanish and an English text (`ai.error.<code>`) and a test iterating the list —
   no failure can surface without a translated, actionable message.
2. `retry_after` is only non-null for `rate_limited` (and never above 60 s where it is used).
3. The provider's own message (`detail`) is redacted of keys and identifiers and truncated to 300
   characters with an ellipsis.
4. `no_credit`, `bad_key` and `model_not_found` are the *blocking* codes: they stop Auto and the
   «continua» path before any provider call.

**Mapping sources** (see `research.md` R2): Anthropic SDK exception classes, bare HTTP status, and
the response body for the markers `maximum context length|context length|too many tokens|prompt is
too long` (context) and `model not exist|model_not_found|no such model|unknown model|invalid model|
model does not exist` (model).

Recorded fixtures used by the tests:

```
DeepSeek 402  {"error":{"message":"Insufficient Balance","type":"insufficient_quota"}}
DeepSeek 400  {"error":{"message":"Model Not Exist","type":"invalid_request_error"}}
Anthropic 429 headers {"retry-after": "7"}
Anthropic 400 {"error":{"message":"prompt is too long: 210321 tokens > 200000 maximum"}}
OpenAI 500    <html>Internal Server Error</html>
```
