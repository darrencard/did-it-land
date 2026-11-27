#!/usr/bin/env python3
"""Regenerate the committed Acme sample: did-it-land.html, its Markdown twin did-it-land.md, and the landed key of
landing/quote-drafting.json.

Inputs, all illustrative (Acme is an invented company): bundle.json (the metric readings), the canonical briefs in
briefs/ (copied from the landing-loop repo, unchanged), and upstream/quote-drafting.json (the loop record as
cost-budget-check left it, filtered to the keys this skill reads: schema, bet, brief and cost). The same inputs give
the same bytes.

Usage, from the repo root:
  python3 examples/acme/sample.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036  (the guard exists for older interpreters)
    raise SystemExit(f"sample: needs Python 3.11 or later; try python3.12 (this is {sys.version.split()[0]}).")

ROOT = Path(__file__).resolve().parents[2]
HERE = Path("examples/acme")
BET = "quote-drafting"


def main() -> int:
    # Start from the record as cost-budget-check left it: this skill reads cost and writes only landed.
    (ROOT / HERE / "landing").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / HERE / "upstream" / f"{BET}.json", ROOT / HERE / "landing" / f"{BET}.json")
    cmd = [
        sys.executable, "skills/did-it-land/scripts/did_it_land.py", "read", str(HERE / "bundle.json"),
        "--loop", str(HERE), "--bet", BET, "--html", str(HERE / "did-it-land.html"), "--md", str(HERE / "did-it-land.md"),
    ]  # fmt: skip
    done = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, check=False)  # noqa: S603  (fixed arguments)
    if done.returncode == 0:
        print(f"sample: wrote did-it-land.html, did-it-land.md and landing/{BET}.json in {HERE}")
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
