# Origo local routing implementation contract

Status: initial gateway and desktop startup integration implemented in `origo_runtime/` and `start_origo_auto.ps1`. Full acceptance remains open. See AUTO_ROUTING_RUNTIME.md for real probe results and limitations. This document records the complete integration contract.

## Stable inference endpoint

Keep one loopback OpenAI-compatible gateway endpoint throughout a conversation. The gateway routes the current request to a text or vision model, without changing stored history or the cached tool schema. Expose route/model/device and timing metadata in diagnostics without logging prompts, keys or attachment bodies.

Automatic selection uses the current attachment content: an image-bearing request selects the tested Qwen2-VL model and its matching projector; ordinary text selects Qwen3.5. A social turn suppresses tool execution using the existing request policy. Explicit unsupported model/image combinations return a useful error; never silently discard an attachment.

Vision preprocessing must use a bounded extraction prompt rather than forwarding the entire agent tool catalog to the smaller vision model. Preserve the attachment and extraction provenance in the task receipt. Any provider-specific representation is generated for that request; it must not mutate persisted messages.

## Runtime ownership and concurrency

One GPU process lease covers loading and the whole inference stream. Concurrent requests queue behind a bounded lock. Launch only the verified signed vendor executable using an argument list; request input must never become a shell command. Stop only a process whose recorded ownership, executable and command line still match. A state file alone does not establish process ownership.

Cancellation must work while queued, loading and streaming. Release leases and terminate owned incomplete loads reliably. Never replay a request after partial output. CPU mode must be selectable; GPU startup failure may retry once on CPU before any output, reporting the degraded mode to the UI. Preserve Docker isolation for execution tools.

## Input and network boundary

Accept only bounded image data URLs with validated MIME, base64 and decoded dimensions. No arbitrary remote URL fetching or local-file reads through an image URL. Bound request size, queue length, response size and timeouts. Return structured errors for malformed JSON, missing model/projector/runtime and permission failures.

Bind to loopback by default. Mobile access belongs to the authenticated private-HTTPS application gateway; do not expose the inference process directly.

## Acceptance evidence

- Real automatic image attachment parsing followed by ordinary text in the same conversation.
- Concurrent text/vision requests and switch-back without GPU process overlap or mixed responses.
- Cancellation at every stage, queue limits, invalid input and missing-file cases.
- Explicit CPU and GPU runs, startup failure recovery, measured cold and warm latency.
- No stored-message mutation, secret/attachment leakage or host-shell fallback.
- UI displays the actual route and runtime state; packaged startup owns all required services.
