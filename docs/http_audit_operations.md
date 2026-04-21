# HTTP Audit Operations Guide

Use this guide when a remote `streamable-http` deployment needs retention planning, replay,
or request-level debugging without persisting raw request bodies.

## What every event carries

- `requestId`: echoed back through `X-Exposure-Audit-Request-Id` for incident correlation.
- `normalizedInputDigestSha256`: stable digest over a redacted, canonical JSON request payload
  that ignores the top-level JSON-RPC `id`.
- `outputDigestSha256`: digest over the JSON-RPC response body for change detection.
- `qualityFlagCodes`, `limitationCodes`, and `manualReviewRequired`: the high-signal trust surface
  needed for screening review without reopening the whole tool payload first.
- `reproducibility.defaultsVersion` and `reproducibility.defaultsHashSha256`: the exact defaults
  pack fingerprint needed to confirm replay compatibility.
- `reproducibility.releaseVersion`, `reproducibility.releaseMetadataPath`, and
  `reproducibility.releaseMetadataSha256`: the release snapshot that should match
  `release://metadata-report` or the checked-in release metadata file.

## Retention and rotation

- Treat the JSONL sink as append-only application evidence, not as a transient debug log.
- Rotate externally with host tooling such as `logrotate`, container log rotation, or explicit
  per-day/per-release paths.
- Keep write permissions narrow because the audit file becomes part of the operational evidence
  trail for HTTP requests.
- Retain enough history to support incident review, release rollback checks, and benchmark drift
  investigation. A reviewed 30- to 90-day retention window is a reasonable default.

## Replay workflow

```bash
python scripts/summarize_http_audit.py /path/to/http-audit.jsonl
python scripts/replay_http_audit.py /path/to/http-audit.jsonl --request-id <request-id>
python scripts/replay_http_audit.py /path/to/http-audit.jsonl --input-digest <sha256>
```

## Reproducibility checklist

1. Match `requestId` to the client-visible response header.
2. Match `defaultsVersion` and `defaultsHashSha256` to `defaults://manifest`.
3. Match `releaseVersion` and the release metadata fields to `release://metadata-report`.
4. Confirm `qualityFlagCodes`, `limitationCodes`, and `manualReviewRequired` still align with the
   downstream interpretation you plan to make.
5. Treat `normalizedInputDigestSha256` as an equivalence key for redacted replay, not as a
   substitute for validated scenario inputs.
