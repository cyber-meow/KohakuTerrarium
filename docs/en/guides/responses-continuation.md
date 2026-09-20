# Stored HTTP Responses continuation

The `codex` backend can connect to an OpenAI-compatible Responses endpoint with
an explicit API key and custom base URL. HTTP requests continue to send full
history with `store=false` by default, including Codex/OAuth endpoints.

For a server that implements stored Responses, opt in using:

```yaml
extra_body:
  http_continuation: true
```

The provider retains a completed response ID and fingerprints of the exact
history and assistant echo. Subsequent turns send only new user/tool items with
`previous_response_id` and `store=true`. Changed history starts a new full-context
request. These controls are client settings and are not forwarded as arbitrary
API fields. The constructor also accepts `http_continuation=True`.

An explicit `previous_response_not_found` or `previous_response_id_not_found`
error before streaming triggers one full-history recovery. Other errors do not
trigger that recovery. A truncated, failed, cancelled, or incomplete response
does not advance the continuation state. Requests are not automatically retried
after text or native tool output has been exposed.

This setting changes server retention and must be enabled only for an endpoint
whose retention and state-routing behavior is appropriate for the application.
Different provider instances and model clones have separate continuation state.
Closing the provider clears its local ID; the endpoint controls server expiry.
Use `websocket_mode: true` separately for connection-local WebSocket continuation.
WebSocket cancellation closes the connection; the next turn reconstructs context.

DeepSeek reasoning replay recognizes routed aliases such as
`cluster/deepseek-v4.1-abl` and `slurm/deepseek-v4.1-abl`.
