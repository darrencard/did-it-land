# Did it land? Ask the metric.

A free Claude skill that reads each shipped bet against its landing brief and says landed, watch or stalled.

![Status words](https://img.shields.io/badge/status-landed%20%2F%20watch%20%2F%20stalled-555)

**Why it matters:** shipping got cheap, so "we shipped it" says little. What matters is whether the metric moved past the bar by the date, and whether that move is real.

**How it works:** Python computes every call and every figure from your own exports, each with its source. Claude writes around the read and never changes it, and a check blocks prose that claims more than the data shows.

## Install: paste this into Claude Code

```text
Install the did-it-land skill from https://github.com/darrencard/did-it-land: clone it, find a Python 3.11 or later on this machine (macOS python3 is often 3.9), run the tests with it (python -m unittest discover -s evals), and copy skills/did-it-land into ~/.claude/skills/did-it-land. Then run a post-launch read on my shipped bets: find each one's landing brief and its metric readings in the tools connected to this session, put them in the two CSVs the skill describes, ask me only for what you cannot find, and show the read exactly as the script prints it.
```

You need Python 3.11 or later; the scripts say so and stop on anything older. Nothing else to install.

## What you get

One table, then one section per bet. From the sample company:

```text
| Payment links | watch | Payment link conversion | 18.1% (2026-11-23) | 18%, 2026-11-30 | Illustrative billing export |

- watch. Past the bar of 18%, but the call is held: within-noise.
- Flag, within-noise: 18.1% is 1.48 times the pre-launch spread (0.8) from the pre-launch
  mean (16.92%), under the 2 needed. Within noise: run an experiment.
- Next step: Run an experiment before calling it: hold the bet back from a random group and
  compare Payment link conversion between the two groups. Correct the status shown in the tracker.
  Decides: Head of Product, Payments squad.
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
- **Bar set after launch:** a brief dated after the ship date is not a test, so it cannot land.

## Try it in one minute

Acme is invented: invoicing software for trades businesses, eight shipped bets, every figure illustrative.

```bash
python3.12 skills/did-it-land/scripts/did_it_land.py read evals/fixtures/acme/bundle.json
```

Your own data: `did_it_land.py init my-read` sets up two CSVs (one row per metric reading, one row per bet) and a briefs folder, and prints the next two commands. Samples are in `evals/fixtures/acme-csv/`.

## Go deeper

- [SKILL.md](skills/did-it-land/SKILL.md): the bundle format, the status rule, every check and its limits.
- The landing brief is the same one the [Product & Technology Leader Report](https://github.com/darrencard/product-engineering-update) uses.
- Python 3.11 or later, standard library only, no network calls. MIT licence.
