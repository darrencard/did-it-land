#!/usr/bin/env python3
"""Turn live data, normalised by the Leader Report's collectors, into did-it-land's metrics.csv.

Live first: fetch the metric with the session's connector (PostHog, Amplitude, Mixpanel, Stripe), save the
response as it stands, and run the matching vendored collector, which writes run/data/<source>.json:

  python3 scripts/vendor/from_posthog.py --insight trend.json --metric "Quote draft acceptance rate" \\
      --period "2026-11-16=2026-11-10..2026-11-16" ... --aggregate mean --project "Acme web" --run run
  python3 scripts/vendor/from_amplitude.py --chart seg.json --metric ... --period ... --aggregate ... --project ... --run run
  python3 scripts/vendor/from_mixpanel.py  --chart insights.json --metric ... --period ... --aggregate ... --project ... --run run
  python3 scripts/vendor/from_stripe.py    --invoices invoices-*.json --months 2026-04..2026-11 --account acme --run run

Then this script reads run/data/analytics.json, warehouse.json and billing.json and writes one metrics.csv
row per metric and period. A period label becomes the reading's date: an ISO date stays as it is, YYYY-MM is
its last day, YYYY-Www its Sunday and YYYY-Qn its last day. Name periods by their last day to keep it simple.
Billing rows become one metric, "ARR", summed over accounts at each month end. The source on every row names
the system, the query and the file, as the collector recorded them. CSV stays the fallback for anything else.

Usage:
  python3 scripts/from_run.py run -o metrics.csv            # append to metrics.csv, or create it

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):  # noqa: UP036  (the guard exists for older interpreters)
    raise SystemExit(f"from_run: needs Python 3.11 or later; this is {sys.version.split()[0]}.")

COLUMNS = ["metric", "date", "value", "source", "last_synced"]
SOURCES = ("analytics", "warehouse", "billing")


class RunError(ValueError):
    """Collected data that cannot be turned into readings. The message lists every problem."""


def period_end(label: str) -> dt.date:
    """The last day a period label covers."""
    label = label.strip()
    # Only a plain YYYY-MM-DD is a date here: Python also reads "2026-W47" as an ISO date (its Monday).
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", label):
        try:
            return dt.date.fromisoformat(label)
        except ValueError:
            raise RunError(f'period "{label}" is not a real date.') from None
    if m := re.fullmatch(r"(\d{4})-(\d{2})", label):
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return dt.date(y, mo, calendar.monthrange(y, mo)[1])
    if m := re.fullmatch(r"(\d{4})-W(\d{2})", label):
        return dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 7)
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", label):
        y, q = int(m.group(1)), int(m.group(2))
        return dt.date(y, q * 3, calendar.monthrange(y, q * 3)[1])
    raise RunError(f'period "{label}" is not a date, YYYY-MM, YYYY-Www or YYYY-Qn. Name the period by its last day.')


def _source(data: dict[str, Any]) -> str:
    parts = [str(data.get("system") or "unknown system")]
    if data.get("query_or_url"):
        parts.append(str(data["query_or_url"]))
    parts.append(f"file {data.get('origin', '?')}, retrieved {data.get('retrieved_at', '?')}")
    return ", ".join(parts)


def rows_from_run(run: Path) -> list[dict[str, Any]]:
    """Readings from every collected source in run/data that did-it-land can read."""
    out: list[dict[str, Any]] = []
    problems: list[str] = []
    found = False
    for name in SOURCES:
        p = run / "data" / f"{name}.json"
        if not p.exists():
            continue
        found = True
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            problems.append(f"cannot read {p} ({e}).")
            continue
        source, synced = _source(data), f"{data.get('retrieved_at', '')}T00:00:00Z" if data.get("retrieved_at") else ""
        if name == "billing":
            by_month: dict[str, float] = {}
            for r in data.get("rows", []):
                by_month[str(r["month"])] = by_month.get(str(r["month"]), 0.0) + float(r["arr"])
            for month, arr in sorted(by_month.items()):
                try:
                    out.append({"metric": "ARR", "date": str(period_end(month)), "value": round(arr, 2), "source": source, "last_synced": synced})
                except RunError as e:
                    problems.append(f"{p.name}: {e}")
            continue
        for r in data.get("rows", []):
            try:
                out.append({"metric": str(r["metric"]), "date": str(period_end(str(r["period"]))), "value": r["value"], "source": source, "last_synced": synced})
            except RunError as e:
                problems.append(f"{p.name}: {e}")
            except KeyError as e:
                problems.append(f"{p.name}: a row has no {e} column.")
    if not found:
        problems.append(f"{run / 'data'} holds none of {', '.join(s + '.json' for s in SOURCES)}. Run a collector first.")
    if problems:
        raise RunError("the collected data cannot be used:\n  " + "\n  ".join(problems))
    return out


def append_csv(rows: list[dict[str, Any]], path: Path) -> None:
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn collected live data (run/data/*.json) into did-it-land's metrics.csv.")
    ap.add_argument("run", help="the run folder the collectors wrote to")
    ap.add_argument("-o", "--out", required=True, help="metrics.csv to append to, or create")
    args = ap.parse_args()
    try:
        rows = rows_from_run(Path(args.run))
    except RunError as e:
        raise SystemExit(f"from_run: {e}") from None
    append_csv(rows, Path(args.out))
    metrics = sorted({r["metric"] for r in rows})
    print(f"from_run: {len(rows)} reading(s) for {len(metrics)} metric(s) ({', '.join(metrics)}) written to {args.out}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
