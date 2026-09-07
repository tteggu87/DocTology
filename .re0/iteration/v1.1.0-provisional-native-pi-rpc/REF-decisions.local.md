# Reviewed starting decisions

The prior dedicated Architect and Critic approved the thin native RPC direction as a small proof, not a default migration. Strongest alternative: the current constrained agent gives clearer read-only/citation guarantees; PTY preserves TUI-only extensions but needs another structured event path. SDK migration adds no benefit to the first Python-backed slice.

Installed inspection baseline: Pi 0.82.1. InteractiveMode and runRpcMode receive the same runtime in installed dist/main.js. RPC supports prompt/abort/get_state/get_messages/get_entries/get_session_stats and extension_ui_request/response. get_entries (not get_session_entries) supplies stable entry IDs and leafId. prompt success means accepted; agent_settled is a turn boundary. TUI custom UI can degrade in RPC and must not be silently treated as equivalent.

Native session metadata/file ownership belongs to Pi. Studio UI masking does not sanitize Pi's own native session files. A cooperative writer lease does not stop external terminals or arbitrary escaped background processes. The first proof uses a disposable vault and never changes the default mode.
