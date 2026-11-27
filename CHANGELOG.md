# Changelog

## 0.3.2, 2026-11-27

- The HTML page follows the Landing Loop sample anatomy: the shared header (mark, DACARD, skill, date, version, blue Illustrative tag), the verdict as the heading ("Quote drafting landed. Job scheduler stalled. Five more are on watch."), every project's line as a small multiple with its status word, one next step (the stalled project first) with the decider in brass, then each project in two columns: its line against the target on the left, its figures and next step on the right. Checks and readings fold under each project; flag codes, brief files, slugs and the record key fold under "For your engineers".
- The signature picture: the metric over time, grey before launch and ink since, against the dashed target line and the due date, with the reading and the status word at the end. The target zone is neutral, never green; the scorecard's green healthy-side band is gone. A 720 wide variant for desktop and a 340 wide one for phones; each aria-label states the answer. Drawn with svgkit, vendored byte-identical from landing-loop and pinned in `VENDORED.json` under `landing-loop`.
- Public copy in plain words: project, target, too close to call, the data source. Held calls print plain reasons ("Past the target of 80%, but not called yet: the data source jumped.").
- The read's figures carry `series`, every reading up to the read, so the page draws the line and prints each point it draws. The `landed` key is unchanged apart from `computed_by`.
- Tests: the pictures draw only printed figures, green and red appear only beside the words landed and stalled, each aria-label states the answer, and public copy uses plain words; the vendored svgkit matches its pin. Two lint findings fixed.
- Fix round 2: no text under 11px at any width. The vendored template and svgkit stay byte-identical; `floor_fonts` raises their smaller sizes to 11px as the page is built, and each project's desktop chart is 640 wide, not 720, so its labels stay 11px in the left column. The header prints the plain name, "Did it land?"; the code name prints only for engineers ("Built by did-it-land 0.3.2.").
- Fix round 2: the Markdown twin uses the page's plain words: project, target, the number, the project file, AI usage per task, and the page's plain checks in place of flag codes. Flag codes, brief files and slugs move to a "For your engineers" section at its end. The README's sample output follows. Tests: no font size under 11px, the header's name, the 640 chart, and no "record", "bet", "bar", "PRD", "ARR" or "tokens" in the public copy of the page or the twin.

## 0.3.1, 2026-11-26

- README: install through the Landing Loop bundle (`/plugin marketplace add darrencard/landing-loop`, then `/plugin install did-it-land@landing-loop`), with the paste-in prompt kept for a standalone install.
- README: the repository is public, so the private-until-review notes are gone, and the loop is counted as eleven skills plus the Product & Technology Leader Report.
- README: one trademark line for Claude and Claude Code.
- The landed call prints cost-budget-check's own budget check beside it and in the next step ("decide whether to scale the bet, given cost is over budget"), cited from the record's `cost` key, never recomputed. The status still comes from the metric alone. `landed.cost_check` records the cited word.
- A next step is never dated before the read: due by the brief's date while it is ahead, else 14 days after the read (`landed.next_step_due`). The sample's quote-drafting step is due 2026-12-10, not 2026-11-15.
- Sample: `examples/acme/sample.py` starts from cost-budget-check's record (`examples/acme/upstream/`) and writes the page, its Markdown twin `did-it-land.md` and the record; a test checks all three byte for byte. `read --md` writes the twin.
- Sample: Acme's pre-launch quote draft readings have a realistic spread (3.83 points), so the move to 41% is 5.05 times the spread, not 25. The 43% read, 41% at the date and the 40% bar are unchanged.
- The page opens with a five-line summary and folds each bet's figures under a details toggle. Selection and focus print in ink, not the template's green. Check chips print in ink.
- The test fixture's other-squad owners read "Lead, Payments squad" and the like; the README labels it a second fixture, separate from the canonical sample.
- Each entry script checks for Python 3.11 first and says "try python3.12".

## 0.3.0, 2026-11-26

- Sample: `examples/acme/did-it-land.html` reads the seven canonical Acme briefs, and `examples/acme/landing/quote-drafting.json` holds the `landed` key. A test regenerates both from the README command byte for byte.
- The page now uses the Leader Report template's own stylesheet (scorecard rows, bullet range line, status marks), so it is the same brand family as the deck.
- `read --bet` and `--html`; an optional `slug` per bet; the record's brief path is relative to the working folder.

## 0.2.0, 2026-11-26

- Step 4 of the Landing Loop: `read --loop` reads each bet's `landing/<bet>.json`, writes only the `landed` key with every figure as value, unit, source, window and as_of, and keeps every other key as it was. `evals` and `cost` show as context; a cost over the brief's budget is flagged; a brief edited after the record opened holds landed.
- Live data first: the Leader Report's PostHog, Amplitude, Mixpanel and Stripe collectors, vendored unchanged at a pinned commit, feed `from_run.py`. CSV stays the fallback.
- `read --out` writes one self-contained HTML page in the Leader Report style, with the Markdown twin and JSON.
- The brief parser, collectors and template are pinned by hash in `VENDORED.json`.
- Fixes: an ISO week label ("2026-W47") is no longer read as its Monday; an outcome with no reading since launch is flagged instead of failing.

## 0.1.0, 2026-11-26

- First version: landed, watch or stalled from the brief's bar and date, with noise, source health, coupling and integrity checks, and the overclaim check.
