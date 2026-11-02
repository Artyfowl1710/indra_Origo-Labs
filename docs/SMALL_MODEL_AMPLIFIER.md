# Pillar 3 — Small-Model Amplifier

## Implemented in this release

- Strict micro-plan validator: exact top-level and step keys, bounded step count and text, unique IDs, and allowlisted step/verifier types.
- Deterministic context packing: relevance-first stable ordering, source labels, truncation metadata, and a hard approximate token budget.
- Cheap verifiers: non-empty output, JSON object/array, numeric comparison, test-summary validation, manual-review state, and arithmetic re-computation using a restricted Python AST (never `eval`).
- API routes under `/api/amplifier/*` for validation, packing, estimates, verification, and capability-profile normalization.

## Important limits

The current token estimator is `ceil(characters / 3)`, not the provider tokenizer. Do not use it for exact billing, model context-limit enforcement, or a published token-efficiency claim. The capability-profile endpoint normalizes already supplied probe results; it does not call a model. The current agent loop does not yet automatically decompose tasks into these typed steps or run validate-and-retry. Best-of-N selection and amplifier-vs-baseline benchmarking remain scaffold-only.

## Example plan

```json
{
  "goal": "Check a simple calculation",
  "steps": [
    {"id":"compute", "type":"compute", "instruction":"Calculate 6 * 7", "verifier":"numeric"},
    {"id":"verify", "type":"verify", "instruction":"Recompute the expression independently", "verifier":"manual"}
  ]
}
```

## API smoke examples

- `GET /api/amplifier/status`
- `POST /api/amplifier/plan/validate` with `{"plan": {"goal":"sum", "steps":[{"id":"calc", "type":"compute", "instruction":"Compute 2+2", "verifier":"numeric"}]}}`
- `POST /api/amplifier/verify/arithmetic` with `{"expression":"6*7", "claimed":42}`
- `POST /api/amplifier/context/pack` with `{"token_budget":100, "items":[{"source":"readme", "relevance":1, "text":"Relevant text"}]}`

## Test scope

`tests/test_amplifier.py` tests validation, packing, verifiers, arithmetic safety, and profile normalization. `tests/test_amplifier_api.py` exercises the API with FastAPI TestClient. These are deterministic harness tests; they are not evidence that a specific small model achieves higher task success.
