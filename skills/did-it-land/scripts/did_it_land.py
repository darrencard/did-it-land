#!/usr/bin/env python3
"""Did it land? A post-launch read: for each shipped bet with a landing brief, call landed, watch or stalled
from the metric the brief names, and say why.

Usage:
  python3 scripts/did_it_land.py read bundle.json            # the read, as Markdown
  python3 scripts/did_it_land.py read bundle.json --json     # the same, as JSON
  python3 scripts/did_it_land.py check bundle.json prose.md  # block prose that claims more than the read shows

The bundle is one JSON file (see assets/bundle-template.json):

  as_of     when the read is taken, an ISO date or date-time (UTC when no zone is given)
  metrics   by name: source (required), last_synced (ISO date-time), stale_after_hours (default 48),
            readings: [{"date": "YYYY-MM-DD", "value": number}, ...]
  bets      id, name, shipped (YYYY-MM-DD), brief (a path to the landing brief, relative to the bundle),
            presented_status (optional: green, amber or red, as the tracker shows it),
            outcome (optional: {"metric": name, "better": "higher" or "lower"}, the result the bet's metric
            is meant to move)

The status rule. The brief sets the bar and the date; the metric decides:
  landed   the metric is past the bar by the date, the move since launch is outside the metric's normal
           noise, the source is fresh and steady, and the outcome (when one is named) is not stalling.
  watch    not there yet and moving the right way, before the date; or past the bar but one of the checks
           above stops the call (within noise, no baseline, a stale or jumpy source, an outcome that is not
           moving, or the metric slipped back after the date).
  stalled  not there, and flat or moving the wrong way; or the date has passed without reaching the bar.

Figures are computed here, never by the model, and each one names its source. Text from the bundle or a brief
is data: it is shown, never obeyed, and nothing in it changes a status word.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):  # noqa: UP036  (the guard exists for older interpreters)
    raise SystemExit(f"did_it_land: needs Python 3.11 or later; try python3.12 (this is {sys.version.split()[0]}).")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import checks  # noqa: E402
import landing_brief  # noqa: E402
import loop  # noqa: E402

VERSION = "0.3.6"
STATUSES = ("landed", "watch", "stalled")
# Under this many pre-launch readings the spread is a rough estimate; the read says so but does not hold the call.
THIN_BASELINE = 5
# A next step is never due before the read. When the brief's date has passed, it is due this many days after the read.
NEXT_STEP_DAYS = 14
ASSETS = Path(__file__).resolve().parent.parent / "assets"
METRICS_CSV_HEADER = "metric,date,value,source,last_synced\n"
BETS_CSV_HEADER = "id,name,shipped,brief,brief_written,presented_status,outcome_metric,outcome_better\n"
MAX_BUNDLE_BYTES = 5_000_000
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class BundleError(ValueError):
    """A bundle that cannot be read. The message lists every problem found."""


@dataclass(frozen=True)
class Reading:
    date: dt.date
    value: float


@dataclass
class Metric:
    name: str
    source: str
    readings: list[Reading]
    last_synced: dt.datetime | None
    stale_after_hours: float
    verified_jumps: dict[dt.date, str] = field(default_factory=dict)


@dataclass
class BetRead:
    id: str
    name: str
    status: str | None  # None only when the bet cannot be read at all (no brief, or no metric data)
    reason: str
    metric: str | None = None
    source: str | None = None
    figures: dict[str, Any] = field(default_factory=dict)
    flags: list[dict[str, str]] = field(default_factory=list)
    next_step: str = ""
    decides: str | None = None
    not_read: str | None = None
    slug: str = ""
    brief_path: str | None = None
    unit: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] | None = None  # cost-budget-check's budget check, cited from the record, never recomputed
    due: str = ""  # when the next step is due: on or after the read date


def clean(text: Any, limit: int = 200) -> str:
    """Source text made safe to show: no control characters, no table-breaking pipes, a length cap."""
    s = CONTROL.sub(" ", str(text)).replace("|", "/").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def parse_when(text: str) -> dt.datetime:
    """An ISO date or date-time as an aware UTC date-time."""
    when = dt.datetime.fromisoformat(text)
    return when.replace(tzinfo=dt.UTC) if when.tzinfo is None else when.astimezone(dt.UTC)


def load_bundle(path: Path) -> tuple[dict[str, Any], dict[str, Metric], dt.datetime]:
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise BundleError(f"cannot read {path} ({e}).") from None
    if len(raw) > MAX_BUNDLE_BYTES:
        raise BundleError(f"{path} is over {MAX_BUNDLE_BYTES:,} bytes, so it is not a bundle.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BundleError(f"{path} is not valid UTF-8 JSON ({e}).") from None
    if not isinstance(data, dict):
        raise BundleError(f"{path} holds no bundle object.")
    problems: list[str] = []
    try:
        as_of = parse_when(str(data.get("as_of", "")))
    except ValueError:
        problems.append('as_of is missing or is not an ISO date, such as "2026-11-26" or "2026-11-26T09:00:00Z".')
        as_of = dt.datetime.now(dt.UTC)
    metrics: dict[str, Metric] = {}
    raw_metrics = data.get("metrics")
    if not isinstance(raw_metrics, dict):
        problems.append("metrics is missing: give an object of metrics by name.")
        raw_metrics = {}
    for name, m in raw_metrics.items():
        label = clean(name, 80)
        if not isinstance(m, dict):
            problems.append(f"metric {label} is not an object.")
            continue
        if not str(m.get("source", "")).strip():
            problems.append(f"metric {label} has no source. Every figure needs one.")
        readings: list[Reading] = []
        for r in m.get("readings") or []:
            try:
                value = r["value"]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise TypeError
                readings.append(Reading(dt.date.fromisoformat(str(r["date"])), float(value)))
            except (KeyError, TypeError, ValueError):
                problems.append(f'metric {label} has a reading that is not {{"date": "YYYY-MM-DD", "value": number}}: {clean(r, 80)}.')
        dates = [r.date for r in readings]
        if len(set(dates)) != len(dates):
            problems.append(f"metric {label} has two readings on the same date.")
        synced = None
        if m.get("last_synced"):
            try:
                synced = parse_when(str(m["last_synced"]))
            except ValueError:
                problems.append(f"metric {label} last_synced is not an ISO date-time.")
        try:
            stale_after = float(m.get("stale_after_hours", checks.STALE_AFTER_HOURS))
        except (TypeError, ValueError):
            problems.append(f"metric {label} stale_after_hours is not a number.")
            stale_after = checks.STALE_AFTER_HOURS
        verified: dict[dt.date, str] = {}
        for v in m.get("verified_jumps") or []:
            try:
                note = str(v["note"]).strip()
                if not note:
                    raise ValueError
                verified[dt.date.fromisoformat(str(v["date"]))] = clean(note, 200)
            except (KeyError, TypeError, ValueError):
                problems.append(f'metric {label} has a verified jump that is not {{"date": "YYYY-MM-DD", "note": who checked it and how}}.')
        metrics[str(name)] = Metric(str(name), clean(m.get("source", ""), 200), sorted(readings, key=lambda r: r.date), synced, stale_after, verified)
    bets = data.get("bets")
    if not isinstance(bets, list) or not bets:
        problems.append("bets is missing or empty.")
    else:
        for i, b in enumerate(bets):
            if not isinstance(b, dict) or not b.get("name"):
                problems.append(f"bet {i + 1} has no name.")
                continue
            if b.get("brief_written") is not None:
                try:
                    dt.date.fromisoformat(str(b["brief_written"]))
                except ValueError:
                    problems.append(f"bet {clean(b['name'], 80)} brief_written must be YYYY-MM-DD.")
            if b.get("presented_status") not in (None, "green", "amber", "red"):
                problems.append(f"bet {clean(b['name'], 80)} presented_status must be green, amber or red.")
            out = b.get("outcome")
            if out is not None and (not isinstance(out, dict) or not out.get("metric") or out.get("better") not in ("higher", "lower")):
                problems.append(f'bet {clean(b["name"], 80)} outcome must be {{"metric": name, "better": "higher" or "lower"}}.')
    if problems:
        raise BundleError("the bundle cannot be read:\n  " + "\n  ".join(problems))
    return data, metrics, as_of


def _latest_on_or_before(readings: list[Reading], day: dt.date) -> Reading | None:
    found = [r for r in readings if r.date <= day]
    return found[-1] if found else None


def _before(readings: list[Reading], r: Reading) -> Reading | None:
    i = readings.index(r)
    return readings[i - 1] if i > 0 else None


def unit_of(brief: landing_brief.Brief) -> str:
    """The unit the brief's bar is written in, for the loop record: %, USD, h, or number."""
    if brief.unit:
        return brief.unit
    return {"$": "USD", "£": "GBP", "€": "EUR"}.get(brief.prefix, "number")


def read_bet(bet: dict[str, Any], metrics: dict[str, Metric], as_of: dt.datetime, base_dir: Path, loop_dir: Path | None = None) -> BetRead:
    """One bet's read. Every figure it prints comes from the bundle; the status word comes from the rule above."""
    out = BetRead(id=clean(bet.get("id", ""), 40), name=clean(bet["name"], 120), status=None, reason="")
    out.slug = loop.slug(str(bet.get("slug") or bet["name"]))
    if not bet.get("brief"):
        out.not_read = "No landing brief, so there is no bar or date to read it against. Write one before the next read."
        return out
    brief_path = (base_dir / str(bet["brief"])).resolve()
    try:
        brief = landing_brief.parse(landing_brief.description_of(brief_path))
    except landing_brief.BriefError as e:
        out.not_read = f"The landing brief cannot be used: {clean(e, 400)}"
        return out
    out.decides = clean(brief.decides, 120)
    out.brief_path = str(brief_path)
    out.unit = unit_of(brief)
    record = None
    if loop_dir is not None:
        try:
            record = loop.load(loop_dir, out.slug)
        except loop.RecordError as e:
            raise BundleError(f"the loop record cannot be read: {e}") from None
        out.context = loop.context(record)
        recorded = ((record or {}).get("brief") or {}).get("sha256")
        if recorded and recorded != loop.sha256(brief_path):
            out.flags.append(
                {
                    "code": "brief-changed",
                    "text": "The brief has changed since the loop record was opened, so the bar may have moved after work began. Restore it, or treat it as a new brief.",
                }
            )
        out.cost = loop.cost_check(record)
        if out.cost and out.cost["budget_status"] == "over budget":
            # Cited from cost-budget-check. It never changes the status, which comes from the metric alone.
            out.flags.append({"code": "over-cost-budget", "text": f"Cost is over budget, cited from {out.cost['cited_from']}. It does not change the status."})
    name, how = checks.match_metric(brief.metric, list(metrics))
    if name is None:
        out.not_read = f'The brief names the metric "{clean(brief.metric, 80)}", and the bundle has no data for it. Export it from the source and read again.'
        return out
    metric = metrics[name]
    out.metric = clean(name, 120)
    out.source = metric.source
    if how == "tokens":
        out.flags.append({"code": "metric-matched-by-name", "text": f'The brief says "{clean(brief.metric, 80)}"; read as "{out.metric}". Confirm it is the same metric.'})
    today = as_of.date()
    by = dt.date.fromisoformat(brief.by)
    try:
        shipped = dt.date.fromisoformat(str(bet.get("shipped", "")))
    except ValueError:
        out.not_read = "The bet has no shipped date (YYYY-MM-DD), so there is no launch to read from."
        return out
    readings = [r for r in metric.readings if r.date <= today]
    current = readings[-1] if readings else None
    if current is None or current.date < shipped:
        out.not_read = f"There is no reading of {out.metric} since the bet shipped on {shipped}. Too early to read."
        return out

    met = (lambda v: v >= brief.bar) if brief.higher_is_better else (lambda v: v <= brief.bar)
    date_passed = today > by
    deciding = _latest_on_or_before(readings, by) if date_passed else current
    if deciding is not None and deciding.date < shipped:
        deciding = None  # a reading from before launch cannot show the bet landed
    figures: dict[str, Any] = {
        "current": {"date": str(current.date), "value": current.value, "shown": brief.show(current.value)},
        "bar": {"value": brief.bar, "shown": brief.bar_text, "better": "higher" if brief.higher_is_better else "lower", "by": brief.by},
        "shipped": str(shipped),
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        # Every reading up to the read, so the page can draw the line and print each point it draws.
        "series": [{"date": str(r.date), "value": r.value, "shown": brief.show(r.value)} for r in readings],
    }
    if date_passed and deciding is not None:
        figures["at_date"] = {"date": str(deciding.date), "value": deciding.value, "shown": brief.show(deciding.value)}

    # The base call, from the bar and the date.
    if deciding is None:
        status, reason = "stalled", f"The date, {brief.by}, passed with no reading of the metric after launch."
    elif met(deciding.value):
        if date_passed and not met(current.value):
            status, reason = "watch", f"It was past the bar at the date ({brief.show(deciding.value)}) and has slipped back since."
            out.flags.append({"code": "slipped-after-date", "text": f"Now {brief.show(current.value)}, back behind the bar of {brief.bar_text}."})
        else:
            status, reason = "landed", f"Past the bar of {brief.bar_text} {'by' if date_passed else 'ahead of'} {brief.by}."
    elif date_passed:
        status, reason = "stalled", f"The date, {brief.by}, has passed and the metric did not reach the bar of {brief.bar_text}."
    else:
        prior = _before(readings, current)
        prior_value = prior.value if prior is not None and prior.date >= shipped else None
        status = landing_brief.status_for(current.value, prior_value, brief.bar, brief.higher_is_better)
        if prior_value is None:
            reason = "Not there yet, and there is no earlier reading since launch to compare, so it is too early to call."
        elif status == "watch":
            reason = f"Not there yet, moving the right way since the last reading ({brief.show(prior_value)}), and {brief.by} has not passed."
        else:
            moved = "flat" if current.value == prior_value else "moving the wrong way"
            reason = f"Not there, and {moved} since the last reading ({brief.show(prior_value)})."

    # Check 1: is the source fresh and steady? (sensor-health.ts)
    fresh_hours = (as_of - metric.last_synced).total_seconds() / 3600 if metric.last_synced else None
    sensor = checks.assess_sensor(fresh_hours, [r.value for r in readings], metric.stale_after_hours)
    figures["source_health"] = {"state": sensor.state, "hours_since_sync": None if fresh_hours is None else round(fresh_hours, 1)}
    if metric.last_synced is None:
        out.flags.append({"code": "no-sync-time", "text": "The bundle gives no last_synced time for this source, so freshness is not checked."})
    if sensor.state == "jumpy" and current.date in metric.verified_jumps:
        out.flags.append({"code": "jump-verified", "text": f"The latest step is large, and was checked: {metric.verified_jumps[current.date]}"})
        sensor = checks.SensorHealth("healthy", "The jump was verified.")
        figures["source_health"]["state"] = "healthy (jump verified)"
    if sensor.state != "healthy":
        out.flags.append({"code": f"source-{sensor.state}", "text": sensor.reason})

    # Was the bar set before the result was known? A bar written after launch is not a test.
    written = bet.get("brief_written")
    if written is None:
        out.flags.append({"code": "brief-date-unknown", "text": "The bundle gives no brief_written date, so the read cannot show the bar was set before launch."})
    elif dt.date.fromisoformat(str(written)) > shipped:
        out.flags.append({"code": "brief-after-launch", "text": f"The brief was written on {written}, after the bet shipped on {shipped}. A bar set after launch is not a test."})

    # Check 2: is the level since launch outside the range the metric held before it?
    # The level test decides; the ported step test (significance.ts) is reported alongside it.
    pre = [r.value for r in readings if r.date < shipped]
    to_value = (deciding or current).value
    level = checks.assess_launch_level(pre, to_value)
    step = checks.assess_significance(pre + [to_value]) if pre else None
    if level is None:
        out.flags.append(
            {
                "code": "no-baseline",
                "text": f"{len(pre)} reading(s) before launch, under the {checks.MIN_BASELINE} needed, so there is no baseline to judge the move against.",
            }
        )
    else:
        flat_baseline = math.isinf(level.z)
        if level.n_baseline < THIN_BASELINE:
            out.flags.append(
                {
                    "code": "thin-baseline",
                    "text": f"The pre-launch spread comes from {level.n_baseline} readings, so the noise band itself is rough. Weigh the noise call lightly.",
                }
            )
        pre_dates = [r.date for r in readings if r.date < shipped]
        figures["move"] = {
            "baseline_from": str(pre_dates[0]),
            "baseline_to": str(pre_dates[-1]),
            "baseline_mean": level.baseline_mean,
            "baseline_sd": level.baseline_sd,
            "baseline_n": level.n_baseline,
            "baseline_shown": brief.show(level.baseline_mean),
            "to": to_value,
            "to_shown": brief.show(to_value),
            "to_date": str((deciding or current).date),
            "delta": level.delta,
            "z": None if flat_baseline else level.z,
            "flat_baseline": flat_baseline,
            "step_z": step.z if step else None,
        }
        good_way = (level.delta > 0) == brief.higher_is_better and level.delta != 0
        if level.within_noise and status != "stalled":
            out.flags.append(
                {
                    "code": "within-noise",
                    "text": f"{brief.show(to_value)} is {abs(level.z):g} times the pre-launch spread ({level.baseline_sd:g}) from the pre-launch mean "
                    f"({brief.show(level.baseline_mean)}), under the {checks.LEVEL_Z:g} needed. Within noise: run an experiment.",
                }
            )
        elif not level.within_noise and not good_way and status != "stalled":
            out.flags.append({"code": "moved-wrong-way", "text": "Since launch the metric has moved the wrong way, outside its pre-launch range."})

    # Check 3: does the outcome move with the metric? (coupling.ts)
    coupling = None
    outcome = bet.get("outcome")
    if outcome:
        oname, _ = checks.match_metric(str(outcome["metric"]), list(metrics))
        if oname is None:
            out.flags.append({"code": "no-outcome-data", "text": f'The outcome "{clean(outcome["metric"], 80)}" has no data in the bundle, so coupling is not checked.'})
        else:
            before_launch = [r for r in readings if r.date < shipped]
            start = before_launch[-1].date if before_launch else shipped
            window = [r for r in readings if r.date >= start]
            o_window = [r for r in metrics[oname].readings if start <= r.date <= today]
        if oname is not None and not o_window:
            out.flags.append(
                {"code": "no-outcome-data", "text": f"{clean(oname, 80)} has no reading since {start}, so coupling is not checked yet. Read again after its next reading."}
            )
        elif oname is not None:
            proxy_sign = 1 if brief.higher_is_better else -1
            coupling = checks.classify_coupling([proxy_sign * r.value for r in window], [r.value for r in o_window], outcome["better"])
            o_first, o_last = (o_window[0].value, o_window[-1].value) if o_window else (None, None)
            figures["outcome"] = {
                "metric": clean(oname, 120),
                "source": metrics[oname].source,
                "from": o_first,
                "to": o_last,
                "window_from": str(o_window[0].date) if o_window else None,
                "window_to": str(o_window[-1].date) if o_window else None,
                "verdict": coupling.verdict,
                "n": coupling.n,
            }
            if coupling.verdict == "decoupled":
                out.flags.append(
                    {
                        "code": "metric-up-outcome-down",
                        "text": f"{out.metric} improved while {clean(oname, 80)} moved the wrong way ({o_first:g} to {o_last:g}). The number is improving and the result is not.",
                    }
                )
            elif coupling.verdict == "flat" and coupling.proxy_delta > 0:
                out.flags.append(
                    {
                        "code": "metric-up-outcome-flat",
                        "text": f"{out.metric} improved while {clean(oname, 80)} held flat ({o_first:g} to {o_last:g}). Check the outcome before crediting the metric.",
                    }
                )
            elif coupling.verdict == "thin":
                out.flags.append({"code": "outcome-thin", "text": f"Fewer than three readings of {clean(oname, 80)} since launch, so coupling is not judged yet."})

    # The caps: a landed call needs every check to pass.
    blockers = {"brief-changed", "brief-after-launch", "source-stale", "source-jumpy", "within-noise", "no-baseline", "metric-up-outcome-down", "metric-up-outcome-flat"}
    held = [f for f in out.flags if f["code"] in blockers]
    if status == "landed" and held:
        status = "watch"
        reason = f"Past the bar of {brief.bar_text}, but the call is held: {', '.join(f['code'] for f in held)}."
    if status == "stalled" and sensor.state != "healthy":
        status = "watch"
        reason = f"The metric reads short of the bar, but the source is {sensor.state}, so the read cannot call it. {reason}"

    # Check 4: does the status the tracker shows sit rosier than the metric? (integrity.ts)
    presented = bet.get("presented_status")
    if presented:
        anchors = [checks.RAG_OF_STATUS[status]]
        if coupling is not None and coupling.verdict == "decoupled":
            anchors.append("red")
        verdict, worst = checks.classify_integrity(presented, anchors)
        figures["integrity"] = {"presented": presented, "anchor": worst, "verdict": verdict}
        if verdict != "aligned":
            under = f"the read is {status}"
            if coupling is not None and coupling.verdict == "decoupled":
                under += " and its outcome is moving the wrong way"
            out.flags.append({"code": verdict.replace(" ", "-"), "text": f"The tracker shows this bet {presented} while {under}."})

    codes = {f["code"] for f in out.flags}
    cost_word = out.cost["budget_status"] if out.cost and out.cost["budget_status"] in loop.BUDGET_WORDS else None
    if status == "landed":
        step = "Keep the metric on the scorecard, and decide whether to scale the bet" + (f", given cost is {cost_word}." if cost_word else ".")
    elif "brief-changed" in codes:
        step = "Put the brief back as it was when the record was opened, or open a new record for the new bar."
    elif "brief-after-launch" in codes:
        step = "Treat this bar as a new brief: date it today and read against it from the next reading."
    elif codes & {"source-stale", "source-jumpy"}:
        step = "Fix or verify the source, then read again. If a jump is real, record who checked it in verified_jumps."
    elif "within-noise" in codes:
        step = f"Run an experiment before calling it: hold the bet back from a random group and compare {out.metric} between the two groups."
    elif "no-baseline" in codes:
        step = "Find pre-launch readings for a baseline, or run an experiment."
    elif codes & {"metric-up-outcome-down", "metric-up-outcome-flat"}:
        step = "Check whether the metric still tracks the outcome before crediting it."
    elif status == "stalled":
        step = "Decide one of three: change course, write a new brief with a new bar and date, or stop the bet."
    else:
        step = f"Read again at the next reading, and by {brief.by} at the latest."
    if "green-over-red" in codes or "one-step-rosier" in codes:
        step += " Correct the status shown in the tracker."
    # A next step is dated on or after the read: the brief's date while it is ahead, else NEXT_STEP_DAYS after the read.
    out.due = str(by if by >= today else today + dt.timedelta(days=NEXT_STEP_DAYS))
    out.status, out.reason, out.figures, out.next_step = status, reason, figures, step
    return out


def read(bundle_path: Path, loop_dir: Path | None = None) -> dict[str, Any]:
    data, metrics, as_of = load_bundle(bundle_path)
    bets = [read_bet(b, metrics, as_of, bundle_path.parent, loop_dir) for b in data["bets"]]
    counts = {s: sum(1 for b in bets if b.status == s) for s in STATUSES}
    counts["not read"] = sum(1 for b in bets if b.status is None)
    return {
        "company": clean(data.get("company", ""), 80),
        "illustrative": bool(data.get("illustrative")),
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "computed_by": f"did-it-land {VERSION}",
        "counts": counts,
        "bets": [b.__dict__ for b in bets],
    }


def landed_key(b: dict[str, Any], as_of: str) -> dict[str, Any]:
    """The `landed` key for one bet's loop record. Every figure carries value, unit, source, window and as_of."""
    f, src, unit = b["figures"], b["source"], b["unit"]
    figs = {"current": loop.figure(f["current"]["value"], unit, src, f["shipped"], f["current"]["date"], as_of)}
    figs["bar"] = loop.figure(f["bar"]["value"], unit, "landing brief: " + Path(b["brief_path"]).name, None, f["bar"]["by"], as_of)
    if "at_date" in f:
        figs["at_date"] = loop.figure(f["at_date"]["value"], unit, src, f["shipped"], f["at_date"]["date"], as_of)
    if "move" in f:
        m = f["move"]
        figs["baseline_mean"] = loop.figure(m["baseline_mean"], unit, src, m["baseline_from"], m["baseline_to"], as_of)
        figs["baseline_sd"] = loop.figure(m["baseline_sd"], unit, src, m["baseline_from"], m["baseline_to"], as_of)
        if m["z"] is not None:
            figs["move_z"] = loop.figure(m["z"], "sd", f"computed from {src}", m["baseline_from"], m["to_date"], as_of)
    if "outcome" in f:
        o = f["outcome"]
        figs["outcome_from"] = loop.figure(o["from"], "number", o["source"], o["window_from"], o["window_from"], as_of)
        figs["outcome_to"] = loop.figure(o["to"], "number", o["source"], o["window_from"], o["window_to"], as_of)
    return {
        "status": b["status"],
        "reason": b["reason"],
        "computed_by": f"did-it-land {VERSION}",
        "as_of": as_of,
        "metric": b["metric"],
        "better": f["bar"]["better"],
        "by": f["bar"]["by"],
        "shipped": f["shipped"],
        "figures": figs,
        "flags": b["flags"],
        "next_step": b["next_step"],
        "next_step_due": b["due"],
        "decides": b["decides"],
        **({"cost_check": {"budget_status": b["cost"]["budget_status"], "cited_from": b["cost"]["cited_from"]}} if b.get("cost") else {}),
    }


def write_loop(result: dict[str, Any], loop_dir: Path, only: str | None = None) -> list[Path]:
    """Write the `landed` key for every bet that was read, or only the one named. A bet not read gets no record."""
    picked = [b for b in result["bets"] if b["status"] and (only is None or b["slug"] == only)]
    if only is not None and not picked:
        raise BundleError(f"no bet read has the slug {only!r}. Slugs: {', '.join(b['slug'] for b in result['bets'] if b['status'])}.")
    return [loop.write(loop_dir, b["slug"], Path(b["brief_path"]), landed_key(b, result["as_of"])) for b in picked]


def to_markdown(result: dict[str, Any]) -> str:
    """The page's Markdown twin, in the page's plain words: project, target, the number. Flag codes, brief files
    and slugs sit under "For your engineers" at the end."""
    from render_html import CHECKS, better_words, figure_tail, past_target, plain, prior_shown  # noqa: PLC0415  (one set of public words for both outputs)

    title = f"Did it land? {result['company']}, read {result['as_of'][:10]}" if result["company"] else f"Did it land? Read {result['as_of'][:10]}"
    c = result["counts"]
    lines = [f"# {title}", ""]
    if result["illustrative"]:
        lines += ["*Illustrative: every figure here is sample data.*", ""]
    lines += [f"{c['landed']} landed, {c['watch']} watch, {c['stalled']} stalled, {c['not read']} not read.", ""]
    lines += ["The scorecard: one row per project, its average before launch, the latest reading and the target.", ""]
    lines += ["| Project | Before launch → now · target | Status |", "|---|---|---|"]
    for b in result["bets"]:
        if b["status"] is None:
            lines.append(f"| {b['name']} | NO READING | not read |")
            continue
        f = b["figures"]
        before = f"{prior_shown(f)} → " if "move" in f else ""
        tail = f" · {figure_tail(f)}" if figure_tail(f) else ""
        why = f", {past_target(b)}" if past_target(b) else ""
        cost = f", cost {b['cost']['budget_status']}" if b.get("cost") else ""
        lines.append(f"| {b['name']} | {before}**{f['current']['shown']}** · TARGET {f['bar']['shown']}{tail} | **{b['status']}**{why}{cost} |")
    for b in result["bets"]:
        lines += ["", f"## {b['name']}: {b['status'] or 'not read'}", ""]
        if b["status"] is None:
            lines.append(plain(b["not_read"]))
            continue
        f = b["figures"]
        cost = f" Cost: {b['cost']['budget_status']}, from the cost check." if b.get("cost") else ""
        lines.append(f"- **{b['status']}**. {plain(b['reason'])}{cost}")
        line = f"- {b['metric']} is {f['current']['shown']} on {f['current']['date']}, against a target of {f['bar']['shown']} {better_words(f)} by {f['bar']['by']}."
        if "at_date" in f:
            line += f" On the due date it read {f['at_date']['shown']} ({f['at_date']['date']})."
        lines.append(line + f" Source: {b['source']}.")
        if "move" in f:
            m = f["move"]
            size = "outside its range before launch, which did not vary" if m["flat_baseline"] else f"{abs(m['z']):g} times its usual ups and downs before launch"
            lines.append(
                f"- Since launch on {f['shipped']}: from an average of {m['baseline_shown']} over {m['baseline_n']} readings before launch "
                f"to {m['to_shown']}, a move of {m['delta']:+g}, {size}."
            )
        if "outcome" in f:
            o = f["outcome"]
            lines.append(f"- The result it should drive, {o['metric']}: {o['from']:g} to {o['to']:g} over the same weeks ({o['n']} readings). Source: {o['source']}.")
        for key, figs in b["context"].items():
            shown = "; ".join(f"{c['name']} {c['value']:,.10g}{' ' + c['unit'] if c['unit'] else ''} ({c['source']})" for c in figs)
            lines.append(f"- From the project file, {key}: {shown}.")
        if b.get("cost"):
            lines.append(f"- The cost check, from the project file: {plain(b['cost']['text'])}.")
        for flag in b["flags"]:
            lines.append(f"- Check: {CHECKS.get(flag['code'], plain(flag['text']))}")
        lines.append(f"- Next step: {plain(b['next_step'])} Decides: {b['decides']}. Due: {b['due']}.")
    lines += ["", "A number moving is not proof that the project moved it. This read says whether the number reached the target, not why."]
    lines += ["", "## For your engineers", "", "| Project | Status | Flag codes | Landing brief | Slug |", "|---|---|---|---|---|"]
    for b in result["bets"]:
        codes = ", ".join(f"`{fl['code']}`" for fl in b["flags"]) or "none"
        brief = Path(b["brief_path"]).name if b.get("brief_path") else "none"
        lines.append(f"| {b['name']} | {b['status'] or 'not read'} | {codes} | {brief} | `{b['slug']}` |")
    for b in result["bets"]:
        if b.get("cost"):
            lines.append(f"\n{b['name']}: the cost word is cited from `{b['cost']['cited_from']}`; the read never recomputes it.")
    lines += [
        "",
        "With --loop and --bet, the read adds its page to the project file: the `landed` key of `landing/<slug>.json`, and no other key. "
        f"Built by {result.get('computed_by', 'did-it-land')}.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the overclaim check

CAUSAL = re.compile(
    r"\b(caused|causes|drove|drives|driven by|because of|thanks to|led to|leads to|resulted in|results in|due to|"
    r"attributable to|responsible for|proves?|proved|proven)\b",
    re.I,
)
SUCCESS = re.compile(r"\b(succeeded|success(?:ful)?|worked|hit (?:its|the) (?:bar|target|goal)|delivered|paid off|on track)\b", re.I)
BANNED = re.compile(r"\b(AI-powered|unlock(?:s|ed|ing)?|supercharg\w*|seamless(?:ly)?|robust|leverag(?:e|es|ed|ing)|get started)\b", re.I)
STATUS_WORD = re.compile(r"\b(landed|watch|stalled)\b", re.I)
NUM = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+Z?)?\b")


def _numbers_in(obj: Any) -> set[float]:
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, int | float):
        found.add(round(float(obj), 2))
        found.add(round(abs(float(obj)), 2))
    elif isinstance(obj, str):
        for tok in NUM.findall(ISO_DATE.sub(" ", obj)):
            found.add(round(abs(float(tok.strip("+-$%").replace(",", ""))), 2))
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= _numbers_in(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _numbers_in(v)
    return found


def check_prose(result: dict[str, Any], prose: str) -> list[dict[str, str]]:
    """Every way the prose claims more than the read shows. Empty when it is safe to send."""
    findings: list[dict[str, str]] = []
    constants = {checks.NOISE_Z, checks.LEVEL_Z, float(checks.MIN_BASELINE)}
    shared = _numbers_in(result["counts"]) | constants
    everything = _numbers_in(result) | constants
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", prose) if s.strip()]
    for s in sentences:
        quoted = s[:120]
        if CAUSAL.search(s):
            findings.append({"rule": "causal-claim", "where": quoted, "fix": "Say the metric moved, not that the bet moved it. A metric moving is not proof."})
        if m := BANNED.search(s):
            findings.append({"rule": "banned-word", "where": quoted, "fix": f'Drop "{m.group(0)}".'})
        named = [b for b in result["bets"] if b["name"].lower() in s.lower()]
        # A sentence that names bets may use only those bets' figures; one that names none may use any.
        allowed = shared.union(*(_numbers_in(b) for b in named)) if named else everything
        for tok in NUM.findall(ISO_DATE.sub(" ", s)):
            value = round(abs(float(tok.strip("+-$%").replace(",", ""))), 2)
            if value not in allowed:
                where = f"in the figures for {', '.join(b['name'] for b in named)}" if named else "in the read"
                findings.append({"rule": "figure-not-computed", "where": quoted, "fix": f"{tok} is not {where}. Use only figures the script computed."})
        for b in named:
            said = {w.lower() for w in STATUS_WORD.findall(s)}
            actual = b["status"] or "not read"
            if said and actual not in said:
                findings.append({"rule": "status-mismatch", "where": quoted, "fix": f"The read calls {b['name']} {actual}. Use that word."})
            if actual != "landed" and SUCCESS.search(s):
                findings.append({"rule": "success-claim", "where": quoted, "fix": f"{b['name']} is {actual}, not landed. Do not call it a success."})
            if not said:
                findings.append({"rule": "status-missing", "where": quoted, "fix": f"Print the status word for {b['name']}: {actual}."})
    return findings


def init(folder: Path) -> int:
    """Set up an empty read: the two CSV headers, a briefs folder with the template, and the next commands."""
    if folder.exists() and any(folder.iterdir()):
        raise SystemExit(f"did_it_land: {folder} is not empty. Pick a new folder so nothing is overwritten.")
    (folder / "briefs").mkdir(parents=True, exist_ok=True)
    (folder / "metrics.csv").write_text(METRICS_CSV_HEADER, encoding="utf-8")
    (folder / "bets.csv").write_text(BETS_CSV_HEADER, encoding="utf-8")
    template = (ASSETS / "landing-brief-template.md").read_text(encoding="utf-8")
    (folder / "briefs" / "example-brief.md").write_text(template, encoding="utf-8")
    here = Path(__file__).resolve().parent
    print(
        f"did_it_land: set up {folder}.\n"
        "  1. One row per metric reading in metrics.csv, with the source on every row.\n"
        "  2. One row per shipped bet in bets.csv; brief is a path such as briefs/my-bet.md.\n"
        "  3. One landing brief per bet in briefs/ (copy example-brief.md).\n"
        f"  4. python3 {here / 'from_csv.py'} {folder / 'metrics.csv'} {folder / 'bets.csv'} --as-of YYYY-MM-DD -o {folder / 'bundle.json'}\n"
        f"  5. python3 {here / 'did_it_land.py'} read {folder / 'bundle.json'}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="A post-launch read: landed, watch or stalled for each shipped bet with a landing brief.")
    ap.add_argument("command", choices=["init", "read", "check"])
    ap.add_argument("bundle", help="init: a new folder to set up; read and check: the bundle JSON")
    ap.add_argument("prose", nargs="?", help="check: a Markdown file of prose written about the read")
    ap.add_argument("--json", action="store_true", help="read: print JSON instead of Markdown")
    ap.add_argument("--loop", help="read: the working folder holding landing/<bet>.json; reads each record, writes only its landed key")
    ap.add_argument("--bet", help="read: with --loop, write only this bet's record (its slug)")
    ap.add_argument("--html", help="read: write the HTML page to this path")
    ap.add_argument("--md", help="read: write the Markdown twin of the page to this path")
    ap.add_argument("--out", help="read: a folder to write read.md, read.html and read.json into")
    args = ap.parse_args()
    if args.command == "init":
        return init(Path(args.bundle))
    try:
        result = read(Path(args.bundle), Path(args.loop) if args.loop else None)
    except BundleError as e:
        raise SystemExit(f"did_it_land: {e}") from None
    if args.command == "read":
        if args.loop:
            try:
                written = write_loop(result, Path(args.loop), args.bet)
            except BundleError as e:
                raise SystemExit(f"did_it_land: {e}") from None
            for p in written:
                print(f"did_it_land: wrote the landed key in {p}", file=sys.stderr)
        if args.html:
            import render_html  # noqa: PLC0415  (only needed for HTML)

            Path(args.html).write_text(render_html.page(result, args.bet), encoding="utf-8")
            print(f"did_it_land: wrote {args.html}", file=sys.stderr)
        if args.md:
            Path(args.md).write_text(to_markdown(result), encoding="utf-8")
            print(f"did_it_land: wrote {args.md}", file=sys.stderr)
        if args.out:
            import render_html  # noqa: PLC0415  (only needed for --out)

            folder = Path(args.out)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "read.md").write_text(to_markdown(result), encoding="utf-8")
            (folder / "read.html").write_text(render_html.page(result, args.bet), encoding="utf-8")
            (folder / "read.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"did_it_land: wrote read.md, read.html and read.json in {folder}", file=sys.stderr)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else to_markdown(result), end="" if not args.json else "\n")
        return 0
    if not args.prose:
        raise SystemExit("did_it_land: check needs the prose file to check.")
    try:
        prose = Path(args.prose).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit(f"did_it_land: cannot read {args.prose} ({e}).") from None
    findings = check_prose(result, prose)
    for f in findings:
        print(f"{f['rule']}: {f['where']}\n  fix: {f['fix']}")
    if findings:
        print(f"did_it_land: {len(findings)} problem(s). Fix the prose; do not change the read.", file=sys.stderr)
        return 1
    print("did_it_land: the prose claims nothing the read does not show.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
