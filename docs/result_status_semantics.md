# Result Status Semantics

## Purpose

- Tool responses keep their existing `structuredContent` payload contracts.
- Future-safe execution state is published separately in top-level tool-result `_meta`.
- The metadata shape follows `toolResultMeta.v1`.

## Current v0.1 Behavior

- `executionMode` is always `sync`.
- `resultStatus` is `completed` for successful calls and `failed` for error results.
- `terminal` is always `true`.
- `queueRequired` is always `false`.
- `jobId` and `statusCheckUri` are `null`.

## Reserved Future States

- `accepted`: a request was accepted for asynchronous execution.
- `running`: execution is still in progress.
- Future async tools should reuse the same keys rather than inventing a second result style.

## Client Guidance

- Read `structuredContent` for the domain object.
- Read top-level `_meta` for execution semantics.
- Do not expect polling or queue semantics from the current deterministic release.
