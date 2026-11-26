"""The Landing Loop record: one JSON file per bet, landing/<bet-slug>.json, shared by five skills and the Leader Report.

did-it-land reads the whole record and writes only its own key, `landed`. Every other key (portfolio, spec,
evals, cost, and any key a later skill adds) is kept exactly as it was found. Every figure written carries
value, unit, source, window (from, to) and as_of. The status word is computed in did_it_land.py, never by the model.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA = "landing-loop/1"
KEY = "landed"
MAX_RECORD_BYTES = 2_000_000


class RecordError(ValueError):
    """A loop record that cannot be used. Nothing is written when this is raised."""


def slug(name: str) -> str:
    """The bet's file name: lower case, words joined by hyphens. "Quote drafting assistant" -> quote-drafting-assistant."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not s:
        raise RecordError(f"the bet name {name!r} has no letters or digits to name its record by.")
    return s[:80]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_for(folder: Path, bet_slug: str) -> Path:
    return folder / "landing" / f"{bet_slug}.json"


def load(folder: Path, bet_slug: str) -> dict[str, Any] | None:
    """The record as it stands, or None when there is none yet. Refused if it is not a landing-loop/1 record for this bet."""
    p = path_for(folder, bet_slug)
    if not p.exists():
        return None
    if p.stat().st_size > MAX_RECORD_BYTES:
        raise RecordError(f"{p} is over {MAX_RECORD_BYTES:,} bytes, so it is not a loop record.")
    try:
        record = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RecordError(f"{p} is not valid JSON ({e}). Fix it or move it; it is never overwritten.") from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise RecordError(f"{p} is not a {SCHEMA} record (its schema is {record.get('schema') if isinstance(record, dict) else None!r}). It is left as it is.")
    if record.get("bet") != bet_slug:
        raise RecordError(f"{p} is the record for {record.get('bet')!r}, not {bet_slug!r}. It is left as it is.")
    return record


def figure(value: Any, unit: str, source: str, window_from: str | None, window_to: str | None, as_of: str) -> dict[str, Any]:
    """One figure in the loop's shape. No figure without a source."""
    if not source:
        raise RecordError("a figure has no source. Every figure in the loop record needs one.")
    return {"value": value, "unit": unit, "source": source, "window": {"from": window_from, "to": window_to}, "as_of": as_of}


def _figures_in(obj: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Every figure-shaped entry (a dict with value and source) inside a key, with its dotted name."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(obj, dict):
        if "value" in obj and "source" in obj:
            return [(prefix or "value", obj)]
        for k, v in obj.items():
            found += _figures_in(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += _figures_in(v, f"{prefix}[{i}]")
    return found


def context(record: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """The figures other skills left in the record, by key, shown beside the read as context. They never change the status."""
    if not record:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for key in ("evals", "cost"):
        figs = _figures_in(record.get(key))
        if figs:
            out[key] = [
                {"name": name, "value": f.get("value"), "unit": f.get("unit", ""), "source": str(f.get("source", "")), "as_of": f.get("as_of")}
                for name, f in figs
                if isinstance(f.get("value"), int | float) and not isinstance(f.get("value"), bool)
            ]
    return {k: v for k, v in out.items() if v}


def cost_figure(record: dict[str, Any] | None, name: str) -> float | None:
    """A cost figure the cost-budget-check skill wrote, by its last name part (tokens_per_task, price_per_token)."""
    for full, f in _figures_in((record or {}).get("cost")):
        if full.split(".")[-1] == name and isinstance(f.get("value"), int | float) and not isinstance(f.get("value"), bool):
            return float(f["value"])
    return None


def write(folder: Path, bet_slug: str, brief_path: Path, landed: dict[str, Any]) -> Path:
    """Write the `landed` key. A new record gets schema, bet and brief; an existing one keeps every other key unchanged."""
    p = path_for(folder, bet_slug)
    record = load(folder, bet_slug)
    if record is None:
        # The brief's path relative to the working folder, so the record reads the same on any machine.
        rel = Path(os.path.relpath(brief_path.resolve(), folder.resolve())).as_posix()
        record = {"schema": SCHEMA, "bet": bet_slug, "brief": {"path": rel, "sha256": sha256(brief_path)}}
    record[KEY] = landed
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p
