"""The deterministic checks behind a post-launch read. Pure functions, standard library only.

Ported from Throughline's analysis layer (TypeScript), kept close to the original so the two agree:

  same_metric, match_metric   metric-match.ts and the token match in landing.ts
  assess_significance         significance.ts: is the latest move inside the metric's normal noise?
  assess_sensor               sensor-health.ts: is the source stale, or did it jump?
  classify_coupling           coupling.ts: is the metric climbing while its outcome stalls?
  classify_integrity          integrity.ts: does a green status sit over a red metric?

No function here reads a file, calls a network or uses randomness. The same input gives the same output.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# A latest move smaller than this many standard deviations of the prior moves is within noise (significance.ts).
NOISE_Z = 1.5
# A latest step more than this many times the median prior step is a jump (sensor-health.ts).
JUMP_FACTOR = 5
# Hours without a fresh reading before a source is stale, unless the metric sets its own (sensor-health.ts).
STALE_AFTER_HOURS = 48
# An outcome move smaller than this share of its own magnitude reads as flat (coupling.ts).
FLAT_BAND = 0.05


def _round(n: float) -> float:
    return round(n * 100) / 100


# ---------------------------------------------------------------- metric-match.ts and landing.ts


def same_metric(a: str, b: str) -> bool:
    """Two metric names refer to the same metric: case- and surrounding-whitespace-insensitive."""
    return a.strip().lower() == b.strip().lower()


def _tokens(s: str | None) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if t]


def match_metric(name: str, candidates: list[str]) -> tuple[str | None, str]:
    """The candidate a brief's metric refers to, and how it matched: "exact", "tokens" or "none".

    An exact match (same_metric) wins. Otherwise the first candidate holding every token of the brief's metric,
    so "activation" matches "Activation rate" (landing.ts matchScorecardRow).
    """
    for c in candidates:
        if same_metric(c, name):
            return c, "exact"
    wanted = _tokens(name)
    if not wanted:
        return None, "none"
    for c in candidates:
        have = _tokens(c)
        if all(t in have for t in wanted):
            return c, "tokens"
    return None, "none"


# ---------------------------------------------------------------- significance.ts


@dataclass(frozen=True)
class Significance:
    latest_delta: float
    sigma: float  # baseline volatility: the standard deviation of the prior period-over-period moves
    z: float  # the latest move, in sigma units
    within_noise: bool
    needs_experiment: bool
    direction: str  # up, down or flat


def assess_significance(trend: list[float] | None) -> Significance | None:
    """Compare the latest move in a trend against the history of the moves before it.

    Needs at least three points (two moves). None when there are fewer.
    """
    if not trend or len(trend) < 3:
        return None
    deltas = [trend[i] - trend[i - 1] for i in range(1, len(trend))]
    latest = deltas[-1]
    prior = deltas[:-1]
    mean = sum(prior) / (len(prior) or 1)
    # With one prior move there is no spread to measure, so its size stands in for it (as significance.ts does).
    variance = sum((d - mean) ** 2 for d in prior) / (len(prior) - 1) if len(prior) > 1 else (abs(mean) or 1)
    sigma = math.sqrt(variance) or 1
    z = latest / sigma
    within = abs(z) < NOISE_Z
    direction = "up" if latest > 1e-4 else "down" if latest < -1e-4 else "flat"
    return Significance(_round(latest), _round(sigma), _round(z), within, within, direction)


# ---------------------------------------------------------------- sensor-health.ts


@dataclass(frozen=True)
class SensorHealth:
    state: str  # healthy, stale or jumpy
    reason: str


def assess_sensor(freshness_hours: float | None, trend: list[float] | None, stale_after_hours: float = STALE_AFTER_HOURS) -> SensorHealth:
    """Grade a source on two failure modes: no fresh reading, and a latest step far larger than its usual step."""
    if freshness_hours is not None and freshness_hours > stale_after_hours:
        return SensorHealth(
            "stale",
            f"No fresh reading in {round(freshness_hours)}h (the limit is {round(stale_after_hours)}h). A stale source reads as health it has not earned.",
        )
    if trend and len(trend) >= 4:
        steps = [abs(trend[i] - trend[i - 1]) for i in range(1, len(trend))]
        prior = sorted(steps[:-1])
        med = prior[len(prior) // 2] if prior else 0
        latest = steps[-1]
        if med > 0 and latest > JUMP_FACTOR * med:
            return SensorHealth(
                "jumpy",
                f"The latest step ({latest:g}) is more than {JUMP_FACTOR} times this source's usual step ({med:g}). Verify the source before trusting it.",
            )
    return SensorHealth("healthy", "Fresh, and the latest step is within the source's usual variation.")


# ---------------------------------------------------------------- coupling.ts


@dataclass(frozen=True)
class Coupling:
    verdict: str  # coupled, flat, decoupled or thin
    proxy_delta: float
    outcome_delta: float  # normalised so a positive number always means the outcome improved
    n: int


def classify_coupling(proxy_trend: list[float], outcome_trend: list[float], outcome_better: str) -> Coupling:
    """Does the outcome move with the metric that is meant to drive it?

    Verdicts (coupling.ts healthy / watch / alarm, renamed so they never read as a status word):
      coupled    the outcome improved alongside the metric, or the metric is not climbing and the outcome held
      flat       the metric climbed and the outcome held flat; or the metric fell and the outcome worsened
      decoupled  the metric climbed while the outcome moved the wrong way
      thin       fewer than three points: too little history to judge
    """
    n = min(len(proxy_trend), len(outcome_trend))
    proxy_delta = proxy_trend[-1] - proxy_trend[0] if len(proxy_trend) >= 2 else 0
    raw = outcome_trend[-1] - outcome_trend[0] if len(outcome_trend) >= 2 else 0
    outcome_delta = -raw if outcome_better == "lower" else raw
    if n < 3:
        return Coupling("thin", proxy_delta, outcome_delta, n)
    base = max([abs(v) for v in outcome_trend] + [1])
    flat = abs(raw) / base < FLAT_BAND
    if proxy_delta <= 0:
        return Coupling("coupled" if outcome_delta >= 0 else "flat", proxy_delta, outcome_delta, n)
    if flat:
        return Coupling("flat", proxy_delta, outcome_delta, n)
    if outcome_delta > 0:
        return Coupling("coupled", proxy_delta, outcome_delta, n)
    return Coupling("decoupled", proxy_delta, outcome_delta, n)


# ---------------------------------------------------------------- integrity.ts

RAG_SEVERITY = {"green": 0, "amber": 1, "red": 2}
RAG_OF_STATUS = {"landed": "green", "watch": "amber", "stalled": "red"}


def classify_integrity(presented: str, anchors: list[str]) -> tuple[str, str]:
    """Compare a presented status (green, amber, red) against the worst of the metrics beneath it.

    Returns (verdict, worst): "green over red" for a two-step gap, "one step rosier" for one, "aligned" otherwise.
    """
    cs = RAG_SEVERITY[presented]
    worst_sev = max((RAG_SEVERITY[a] for a in anchors), default=0)
    worst = next(k for k, v in RAG_SEVERITY.items() if v == worst_sev)
    gap = worst_sev - cs
    if gap >= 2:
        return "green over red", worst
    if gap == 1:
        return "one step rosier", worst
    return "aligned", worst
