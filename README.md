# Did it land? Ask the metric.

A free Claude skill that reads each shipped bet against its landing brief and says landed, watch or stalled.

![Status words](https://img.shields.io/badge/status-landed%20%2F%20watch%20%2F%20stalled-555)

**Why it matters:** shipping got cheap, so "we shipped it" says little. What matters is whether the metric moved past the bar by the date, and whether that move is real.

**How it works:** Python computes every call and every figure from your own exports, each with its source. Claude writes around the read and never changes it, and a check blocks prose that claims more than the data shows.

## Install: paste this into Claude Code

```text
Install the did-it-land skill from https://github.com/darrencard/did-it-land: clone it, run python3 -m unittest discover -s evals to check it, and copy skills/did-it-land into ~/.claude/skills/did-it-land. Then run a post-launch read on my shipped bets: find each one's landing brief and its metric data in the tools connected to this session, ask me only for what you cannot find, and show the read exactly as the script prints it.
```

## What it calls

| Word | When |
|---|---|
| **landed** | Past the bar by the date, outside the metric's normal noise, from a fresh source, with the outcome not stalling |
| **watch** | Moving the right way before the date, or past the bar with a check holding the call |
| **stalled** | Flat or moving the wrong way, or the date passed short of the bar |

## What it flags

- **Within noise:** the move is inside the metric's usual week-to-week variation. Next step: run an experiment.
- **Stale or jumpy source:** no fresh reading, or a step far larger than usual. Verify before trusting it.
- **Metric up, outcome down:** the number improves while the result it should move does not.
- **Green over red:** the tracker shows green while the read is stalled.

## Try it on the sample company

Acme is invented: invoicing software for trades businesses, eight shipped bets, every figure illustrative.

```bash
python3 skills/did-it-land/scripts/did_it_land.py read evals/fixtures/acme/bundle.json
```

## Go deeper

- [SKILL.md](skills/did-it-land/SKILL.md): the bundle format, the status rule, every check and its limits.
- The landing brief is the same one the [Product & Technology Leader Report](https://github.com/darrencard/product-engineering-update) uses.
- Python 3.11 or later, standard library only, no network calls. MIT licence.
