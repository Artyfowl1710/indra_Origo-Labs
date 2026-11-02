# Origo Outcome Review (v1.6)

## Purpose

Run-linked assistant answers now also carry a quiet calibration note: trace/evidence artifacts aid inspection but do not guarantee correctness. This avoids presenting confidence or a signed artifact as proof of truth.

Outcome Review lets a user leave one lightweight rating on a completed assistant run: **Useful**, **Incorrect**, **Incomplete**, or **Risky / unsafe**. This is a human-reported signal for reviewing a local session, not an objective quality benchmark.

## Interaction contract

- Ratings are optional. A user can ignore the controls, change a selection, remove a selection, or clear all ratings.
- A single rating is stored per run; selecting a different value replaces the earlier value.
- The rating is associated with the saved conversation and run ID, not the prompt or answer text.
- Ratings are stored in Origo's local SQLite database. They are not sent to the model, used for training, or used to automatically change prompts, routing, or behavior.
- Clearing ratings never deletes run history, answer text, or conversations. Deleting a conversation removes its associated ratings.
- The UI shows counts and labels ratings as self-reported. It deliberately avoids a percentage called “accuracy” or “success”.
- Retention is bounded to the most recent 5,000 ratings. Older ratings may be discarded as new ones arrive.

## API

- `GET /api/feedback`: aggregate counts only. Include an explicit `conversation_id` query parameter to retrieve run-ID-to-rating labels for that one saved conversation. Neither form includes prompts or answers.
- `POST /api/feedback`: body includes `run_id`, `conversation_id`, and a rating from the four-value allowlist. The server checks that the run is an assistant message in the named conversation.
- `DELETE /api/feedback/{run_id}?conversation_id=...`: removes one rating while keeping the run and conversation.
- `DELETE /api/feedback`: clear every local rating.

## What this does not claim

It is not a user study, does not identify why a model failed, does not provide calibrated confidence, and does not improve the model automatically. Feedback trends should only inform a future product decision after review. A small number of voluntary ratings is biased toward users and runs that people choose to rate.

## Acceptance tests

`tests/test_feedback.py` verifies valid/invalid ratings, per-conversation run membership, replacement, deletion, clear-all behavior, conversation deletion cleanup, the absence of answer/prompt text in feedback summaries, and zero model calls when a rating is submitted. `tests/test_hmi.py` checks that the UI keeps rating optional and explains the data flow.
