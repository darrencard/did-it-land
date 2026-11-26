#!/usr/bin/env python3
"""Build a did-it-land bundle from two CSV files, so nobody hand-writes JSON.

Usage:
  python3 scripts/from_csv.py metrics.csv bets.csv --as-of 2026-11-26 -o bundle.json

metrics.csv, one row per reading (the shape most analytics and BI exports already have):
  metric, date, value, source, last_synced (optional), stale_after_hours (optional)
  A metric's source must be the same on every row. last_synced is the latest one given.

bets.csv, one row per shipped bet:
  id, name, shipped, brief, brief_written (optional), presented_status (optional),
  outcome_metric (optional), outcome_better (optional: higher or lower)
  brief is a path to the landing brief, relative to the bundle you write.

Every problem in both files is listed at once. The bundle is then checked by did_it_land.py, so a bundle this
writes is one the read accepts. Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):  # noqa: UP036  (the guard exists for older interpreters)
    raise SystemExit(f"from_csv: needs Python 3.11 or later; this is {sys.version.split()[0]}.")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import did_it_land  # noqa: E402

METRIC_COLUMNS = {"metric", "date", "value", "source"}
BET_COLUMNS = {"id", "name", "shipped", "brief"}


def _rows(path: Path, required: set[str], problems: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = {h.strip().lower() for h in reader.fieldnames or []}
            if missing := required - header:
                problems.append(f"{path.name} is missing column(s): {', '.join(sorted(missing))}.")
                return []
            return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        problems.append(f"cannot read {path} ({e}).")
        return []


def build(metrics_csv: Path, bets_csv: Path, as_of: str, company: str = "", illustrative: bool = False) -> dict[str, Any]:
    problems: list[str] = []
    metrics: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(_rows(metrics_csv, METRIC_COLUMNS, problems), start=2):
        name = row["metric"]
        if not name:
            problems.append(f"{metrics_csv.name} line {i}: metric is empty.")
            continue
        try:
            value = float(row["value"].replace(",", ""))
        except ValueError:
            problems.append(f"{metrics_csv.name} line {i}: value {row['value']!r} is not a number.")
            continue
        m = metrics.setdefault(name, {"source": row["source"], "readings": []})
        if row["source"] and m["source"] and row["source"] != m["source"]:
            problems.append(f"{metrics_csv.name} line {i}: {name} has two sources ({m['source']!r} and {row['source']!r}). Keep one per metric.")
        m["source"] = m["source"] or row["source"]
        if row.get("last_synced") and row["last_synced"] > m.get("last_synced", ""):
            m["last_synced"] = row["last_synced"]
        if row.get("stale_after_hours"):
            try:
                m["stale_after_hours"] = float(row["stale_after_hours"])
            except ValueError:
                problems.append(f"{metrics_csv.name} line {i}: stale_after_hours is not a number.")
        m["readings"].append({"date": row["date"], "value": value})
    bets: list[dict[str, Any]] = []
    for i, row in enumerate(_rows(bets_csv, BET_COLUMNS, problems), start=2):
        bet: dict[str, Any] = {"id": row["id"], "name": row["name"], "shipped": row["shipped"], "brief": row["brief"] or None}
        for key in ("brief_written", "presented_status"):
            if row.get(key):
                bet[key] = row[key].lower() if key == "presented_status" else row[key]
        if row.get("outcome_metric"):
            bet["outcome"] = {"metric": row["outcome_metric"], "better": (row.get("outcome_better") or "").lower()}
        if not row["name"]:
            problems.append(f"{bets_csv.name} line {i}: name is empty.")
        bets.append(bet)
    if problems:
        raise did_it_land.BundleError("the CSV files cannot be used:\n  " + "\n  ".join(problems))
    return {"company": company, "illustrative": illustrative, "as_of": as_of, "metrics": metrics, "bets": bets}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a did-it-land bundle from a metrics CSV and a bets CSV.")
    ap.add_argument("metrics_csv")
    ap.add_argument("bets_csv")
    ap.add_argument("--as-of", required=True, help="when the read is taken: YYYY-MM-DD or an ISO date-time")
    ap.add_argument("-o", "--out", required=True, help="the bundle JSON to write; brief paths are relative to it")
    ap.add_argument("--company", default="")
    ap.add_argument("--illustrative", action="store_true", help="mark every figure as sample data")
    args = ap.parse_args()
    out = Path(args.out)
    try:
        bundle = build(Path(args.metrics_csv), Path(args.bets_csv), args.as_of, args.company, args.illustrative)
        out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = did_it_land.read(out)
    except did_it_land.BundleError as e:
        raise SystemExit(f"from_csv: {e}") from None
    c = result["counts"]
    print(
        f"from_csv: wrote {out}: {len(bundle['metrics'])} metrics, {len(bundle['bets'])} bets. "
        f"{c['landed']} landed, {c['watch']} watch, {c['stalled']} stalled, {c['not read']} not read.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
