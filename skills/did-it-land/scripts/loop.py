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
    """The figures eval-kit left in the record, shown beside the read as context. They never change the status.

    `cost` is not listed here: its budget check is cited whole by cost_check(), never re-listed or recomputed.
    """
    if not record:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for key in ("evals",):
        figs = _figures_in(record.get(key))
        if figs:
            out[key] = [
                {"name": name, "value": f.get("value"), "unit": f.get("unit", ""), "source": str(f.get("source", "")), "as_of": f.get("as_of")}
                for name, f in figs
                if isinstance(f.get("value"), int | float) and not isinstance(f.get("value"), bool)
            ]
    return {k: v for k, v in out.items() if v}


BUDGET_WORDS = ("within budget", "over budget")
COST_LINES = (("cost_per_task", "cost per task"), ("tokens_per_task", "tokens per task"), ("price_per_token", "price per token"))


def _num(f: Any) -> float | None:
    v = f.get("value") if isinstance(f, dict) else None
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _shown(value: float, unit: str) -> str:
    """A figure as cost-budget-check wrote it, formatted for reading. Formatting only: nothing is recomputed."""
    if unit.startswith("USD"):
        text = f"{value:.8f}" if abs(value) < 0.01 else f"{value:.4f}"
        return "$" + text.rstrip("0").rstrip(".")
    if unit.startswith("tokens"):
        return f"{value:,.0f}"
    return f"{value:,.6g}"


def cost_check(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """cost-budget-check's own budget check, cited from the record's `cost` key and never recomputed.

    None when the record holds no `cost` key. When the key holds no budget word, the check reads "not checked".
    Each line keeps cost-budget-check's word, its actual and budget figures, and its share over or under budget.
    """
    cost = (record or {}).get("cost")
    if not isinstance(cost, dict):
        return None
    tool = str(cost.get("tool") or "cost-budget-check")[:80]
    word = cost.get("budget_status")
    if word not in BUDGET_WORDS:
        return {"budget_status": "not checked", "cited_from": tool, "lines": [], "window": None, "text": "cost not checked: run cost-budget-check"}
    lines = []
    window = None
    for key, label in COST_LINES:
        ln = (cost.get("lines") or {}).get(key)
        if not isinstance(ln, dict):
            continue
        actual, budget, share = _num(ln.get("actual")), _num(ln.get("budget")), _num(ln.get("against_budget"))
        if actual is None or budget is None or ln.get("budget_status") not in BUDGET_WORDS:
            continue
        unit = str(ln["actual"].get("unit", ""))
        window = window or (ln["actual"].get("window") or {})
        line = {"name": label, "budget_status": ln["budget_status"], "actual": _shown(actual, unit), "budget": _shown(budget, unit), "unit": unit}
        if share is not None:
            line["share"] = f"{abs(share) * 100:.0f}% {'over' if share > 0 else 'under'}"
        lines.append(line)
    parts = [f"{ln['name']} {ln['actual']} against {ln['budget']}" + (f", {ln['share']}" if "share" in ln else "") for ln in lines]
    when = f", {window.get('from')} to {window.get('to')}" if window and window.get("from") else ""
    text = f"{word} ({tool}{when})" + (": " + "; ".join(parts) if parts else "")
    return {"budget_status": word, "cited_from": tool, "lines": lines, "window": window, "text": text}


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
