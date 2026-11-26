# Changelog

## 0.2.0, 2026-11-26

- Step 4 of the Landing Loop: `read --loop` reads each bet's `landing/<bet>.json`, writes only the `landed` key with every figure as value, unit, source, window and as_of, and keeps every other key as it was. `evals` and `cost` show as context; a cost over the brief's budget is flagged; a brief edited after the record opened holds landed.
- Live data first: the Leader Report's PostHog, Amplitude, Mixpanel and Stripe collectors, vendored unchanged at a pinned commit, feed `from_run.py`. CSV stays the fallback.
- `read --out` writes one self-contained HTML page in the Leader Report style, with the Markdown twin and JSON.
- The brief parser, collectors and template are pinned by hash in `VENDORED.json`.
- Fixes: an ISO week label ("2026-W47") is no longer read as its Monday; an outcome with no reading since launch is flagged instead of failing.

## 0.1.0, 2026-11-26

- First version: landed, watch or stalled from the brief's bar and date, with noise, source health, coupling and integrity checks, and the overclaim check.
