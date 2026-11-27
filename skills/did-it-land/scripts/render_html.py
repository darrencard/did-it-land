"""The read as one self-contained HTML page, in the Leader Report style guide and the Landing Loop's one visual family.

The page uses the report's own stylesheet, taken whole from its template (assets/vendor/template.html, vendored
byte-identical at a pinned commit), and draws its pictures with svgkit (scripts/vendor/svgkit.py, vendored
byte-identical from landing-loop). Only a few rules for this page's layout are added.

The page reads top down for someone who has never seen the loop: the shared header, the verdict as the heading,
every project's line against its target, then one thing to do next. Each project follows in two columns, the line
on the left and its figures on the right. Checks sit in a fold, and flag codes, file names and the record key sit
in a last fold for engineers. Public copy uses plain words: project, target, too close to call.

Colour means one thing each: green and red only inside the printed words landed and stalled, brass for the person
who decides, grey for the time before launch and ink for the time since. The target zone is neutral, never green.
Each picture draws only figures the page prints, and its aria-label states the answer.

Nothing is loaded from the network, nothing in the output depends on the clock or the machine, and every piece
of text from a source is escaped.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

import svgkit as sk  # noqa: E402  (vendored, unchanged; see VENDORED.json)

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)
CHART_WIDE = 640  # the desktop chart's viewBox width, for the two-column layout

# Layout for this page only. Everything else comes from the template's stylesheet and svgkit.CSS.
PAGE_CSS = """
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{min-height:0;padding-top:40px;padding-bottom:48px;justify-content:flex-start}
.solo h1{font-size:clamp(34px,4.6vw,60px);line-height:1;letter-spacing:-.04em;max-width:22ch;margin-bottom:20px}
.solo .lede{margin-bottom:28px}
.solo .lede b{color:var(--t1);font-weight:500}
.minis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--s1)}
.mini{display:flex;flex-direction:column;gap:10px;padding:16px 18px 18px;text-decoration:none;color:var(--t1);box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line)}
.mini:hover{background:var(--s2)}
.mini-h{display:flex;justify-content:space-between;align-items:baseline;gap:10px;font-size:14px;line-height:1.3}
.mini-f{font:400 11px/16px var(--mono);color:var(--t3);font-variant-numeric:tabular-nums}
.mini-f b{color:var(--t1);font-weight:500;font-size:13px}
.mini-f span{display:block}
.mini.key{justify-content:center;gap:12px;color:var(--t2)}
.mini.key .mini-f{display:flex;align-items:center;gap:10px}
.next{margin-top:28px;display:grid;grid-template-columns:200px minmax(0,1fr);gap:8px 32px;align-items:baseline;border:1px solid var(--brass);border-radius:12px;padding:20px 24px;background:var(--brass-bg)}
.next>b{font:400 11px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--brass)}
.next p{margin:0;font-size:16px;line-height:1.5;color:var(--t1)}
.next .who{display:flex;flex-wrap:wrap;gap:4px 24px;margin-top:10px;font:400 11.5px/16px var(--mono);color:var(--brass)}
.next .who span::before{font-size:11px;letter-spacing:.1em;color:var(--t3);margin-right:8px}
.next .who .o::before{content:"DECIDES"}.next .who .d::before{content:"DUE"}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:10px 24px}
.head h2{margin-bottom:12px}
.head .marks{display:flex;align-items:baseline;gap:12px}
.chip{font:400 11px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t1);border:1px solid var(--line2);border-radius:3px;padding:1px 6px;white-space:nowrap}
.cols{display:grid;grid-template-columns:minmax(0,2.4fr) minmax(260px,1fr);gap:24px 40px;align-items:start;margin-top:4px}
.figs{margin:0;display:grid}
.figs>div{display:grid;grid-template-columns:112px minmax(0,1fr);gap:4px 16px;border-top:1px solid var(--line);padding:11px 0}
.figs dt{font:400 11px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.figs dd{margin:0;font-size:13.5px;line-height:1.55;color:var(--t2)}
.figs dd b{color:var(--t1);font-weight:500}
.figs .own dt,.figs .own .o{color:var(--brass)}
.figs .own .o,.figs .own .d{display:block;font:400 11.5px/18px var(--mono);margin-top:4px}
.figs .own .d{color:var(--t2)}
.solo details{margin-top:24px}
.checks{margin:12px 0 0;padding:0;list-style:none;max-width:80ch}
.checks li{border-top:1px solid var(--line);padding:9px 0;font-size:13.5px;color:var(--t2)}
.readings{margin-top:16px;max-width:520px}
.readings td,.readings th{padding:7px 14px}
.eng td{font-size:12px}
.eng .chip{margin:0 6px 4px 0;display:inline-block}
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:1100px){.cols{grid-template-columns:minmax(0,1fr)}.minis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:980px){.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:24px}.next{grid-template-columns:1fr}}
@media (max-width:560px){.mini{padding:12px 12px 14px;gap:8px}.mini-h{flex-direction:column;gap:2px;font-size:13px}.mini-f{font-size:11px}.figs>div{grid-template-columns:1fr;gap:0}}
"""

NUMBER_WORDS = ("No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve")

# A held call, in plain words. The codes themselves print only in the engineers' fold.
HELD = {
    "within-noise": "too close to call",
    "source-stale": "the data source is out of date",
    "source-jumpy": "the data source jumped",
    "metric-up-outcome-down": "the result it should drive fell",
    "metric-up-outcome-flat": "the result it should drive held flat",
    "brief-changed": "the plan changed after work began",
    "brief-after-launch": "the target was set after launch",
    "no-baseline": "there are no readings from before launch to compare",
}

# Each check, in plain words. Unknown codes fall back to the read's own text.
CHECKS = {
    "over-cost-budget": "Cost is over budget, from the cost check. It never changes the status.",
    "thin-baseline": "Only a few readings came before launch, so its usual range is a rough guess.",
    "within-noise": "Too close to call: since launch the number sits inside the ups and downs it had before launch.",
    "source-stale": "The data source is out of date, so the read cannot trust the last reading.",
    "source-jumpy": "The last reading jumped far more than this source usually moves. Check the source before trusting it.",
    "metric-up-outcome-down": "The number rose, but the result it should drive fell.",
    "metric-up-outcome-flat": "The number rose, but the result it should drive held flat.",
    "green-over-red": "The tracker shows this project green, which is rosier than this read.",
    "one-step-rosier": "The tracker shows this project green, one step rosier than this read.",
    "brief-changed": "The landing brief changed after work began, so the target may have moved.",
    "brief-after-launch": "The target was written after launch, so it is not a fair test.",
    "brief-date-unknown": "The read cannot show the target was set before launch: the brief has no date.",
    "no-baseline": "There are too few readings from before launch to judge the move.",
    "moved-wrong-way": "Since launch the number has moved the wrong way, outside its usual range.",
    "slipped-after-date": "It passed the target by the due date and has slipped back since.",
    "no-sync-time": "The data has no last-updated time, so freshness was not checked.",
    "jump-verified": "The last reading jumped, and a named person checked it.",
    "metric-matched-by-name": "The brief names the metric slightly differently. Confirm it is the same one.",
    "no-outcome-data": "No data yet for the result it should drive.",
    "outcome-thin": "Too few readings of the result it should drive to judge it yet.",
}

WORDS = (
    (r"\bthe bets\b", "the projects"),
    (r"\bbets\b", "projects"),
    (r"\bthe bet\b", "the project"),
    (r"\bbet\b", "project"),
    (r"\ba new brief with a new bar\b", "a new landing brief with a new target"),
    (r"\bthe bar\b", "the target"),
    (r"\bbar\b", "target"),
    (r" If a jump is real, record who checked it in verified_jumps\.", " If the jump is real, note who checked it."),
    (r"\bthe loop record\b", "the project file"),
    (r"\ba new record\b", "a new project file"),
    (r"\bthe record\b", "the project file"),
    (r"\btokens per task\b", "AI usage per task"),
    (r"\bprice per token\b", "AI price per unit"),
    (r"\bthe source\b", "the data source"),
    (r"\bthe metric\b", "the number"),
)


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def plain(text: str) -> str:
    """The read's own sentences in the page's words: project, target. Held codes become plain clauses."""
    held = re.search(r"the call is held: ([a-z, -]+)\.$", text)
    if held:
        why = [HELD.get(c.strip(), c.strip()) for c in held.group(1).split(",")]
        lead = "" if why == ["too close to call"] else "not called yet: "
        text = text[: held.start()] + lead + "; ".join(why) + "."
    for pattern, to in WORDS:
        text = re.sub(pattern, to, text)
    return text


FONT_FLOOR = 11  # px: no text on the page renders smaller, at any width
FONT_SIZE = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)px")
FONT_SHORTHAND = re.compile(r"(font\s*:[^;{}]*?)(?<![\w.-])(\d+(?:\.\d+)?)px")


def floor_fonts(css: str) -> str:
    """Raise every font size under 11px to 11px. The vendored template and svgkit stay byte-identical on disk;
    the floor applies to their text as the page is built, so this page's CSS has no smaller size anywhere."""

    def up(m: re.Match[str]) -> str:
        return f"{m.group(1)}{FONT_FLOOR if float(m.group(2)) < FONT_FLOOR else m.group(2)}px"

    return FONT_SHORTHAND.sub(up, FONT_SIZE.sub(up, css))


def stylesheet() -> str:
    """The report template's whole stylesheet, fonts included."""
    try:
        found = STYLE.search(TEMPLATE.read_text(encoding="utf-8"))
    except OSError:
        found = None
    return found.group(1) if found else ""


def status_mark(status: str | None) -> str:
    """The status mark, as the template draws it. The word always prints."""
    if status is None:
        return '<span class="st watch" style="color:var(--t3)">not read</span>'
    return f'<span class="st {e(status)}">{e(status)}</span>'


def and_join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def count_word(n: int) -> str:
    return NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else str(n)


def verdict(result: dict[str, Any]) -> str:
    """The heading: who landed, who stalled, how many are on watch."""
    bets = result["bets"]
    by = {w: [b["name"] for b in bets if b["status"] == w] for w in ("landed", "stalled", "watch")}
    parts = [f"{and_join(by[w])} {w}." for w in ("landed", "stalled") if by[w]]
    if by["watch"]:
        n = len(by["watch"])
        parts.append(f"{count_word(n)}{' more' if parts else ''} {'is' if n == 1 else 'are'} on watch.")
    unread = sum(1 for b in bets if b["status"] is None)
    if unread:
        parts.append(f"{count_word(unread)} could not be read.")
    return " ".join(parts) or "No project could be read."


def _day(text: str) -> int:
    return dt.date.fromisoformat(text).toordinal()


def better_words(f: dict[str, Any]) -> str:
    return "or higher" if f["bar"]["better"] == "higher" else "or lower"


def _scales(f: dict[str, Any], x_to: tuple[float, float], y_to: tuple[float, float], pad: float) -> tuple[Any, Any]:
    days = [_day(r["date"]) for r in f["series"]] + [_day(f["shipped"]), _day(f["bar"]["by"])]
    values = [r["value"] for r in f["series"]] + [f["bar"]["value"]]
    lo, hi = min(values), max(values)
    room = (hi - lo) * pad or abs(hi) * 0.1 or 1
    return sk.scale((min(days), max(days)), x_to), sk.scale((lo - room, hi + room), y_to)


def _lines(f: dict[str, Any], x: Any, y: Any) -> tuple[list[str], tuple[float, float]]:
    """Grey before launch, ink since, joined at the last reading before launch."""
    pre = [(x(_day(r["date"])), y(r["value"])) for r in f["series"] if r["date"] < f["shipped"]]
    post = [(x(_day(r["date"])), y(r["value"])) for r in f["series"] if r["date"] >= f["shipped"]]
    parts = []
    if len(pre) > 1:
        parts.append(sk.line_series(pre, tone=sk.MUTED))
    if post:
        parts.append(sk.line_series(pre[-1:] + post, tone=sk.INK, width=2))
    return parts, (post or pre)[-1]


def chart(b: dict[str, Any], variant: str) -> str:
    """The signature picture: the metric over time against the target and the due date. Grey before launch, ink
    since. The target zone is neutral. The status word prints at the end of the line."""
    f = b["figures"]
    wide = variant == "wide"
    # 640 wide on desktop, not svgkit's 720: the chart sits in the left of two columns, and at 640 its 11px labels
    # stay 11px or larger at every width the two columns show.
    width, height = (CHART_WIDE, 250) if wide else (sk.TALL, 262)
    left, right, top, bottom = 0.0, (CHART_WIDE - 124.0 if wide else 246.0), 30.0, (192.0 if wide else 186.0)
    x, y = _scales(f, (left + 6, right - 6), (bottom, top), 0.16)
    ty, xs, xb = y(f["bar"]["value"]), x(_day(f["shipped"])), x(_day(f["bar"]["by"]))
    # The target zone: the side of the target where it is met, shaded neutral.
    higher = f["bar"]["better"] == "higher"
    parts = [sk.zone(left, top - 12, right - left, ty - top + 12) if higher else sk.zone(left, ty, right - left, bottom + 12 - ty)]
    parts.append(sk.rule(left, bottom + 12, right, bottom + 12))
    parts.append(sk.rule(xs, top - 12, xs, bottom + 12, tone=sk.LINE3, dashed=True))
    parts.append(sk.deadline(xb, top - 12, bottom + 12))
    parts.append(sk.target_line(left, right, ty))
    target_text = f"Target {f['bar']['shown']}"
    tw = sk.label_width(target_text) + 12
    # The target's label sits at the left end unless the launch or due line would cross it there.
    at_left = not any(left < v < left + tw for v in (xs, xb)) or any(right - tw < v < right for v in (xs, xb))
    parts.append(sk.label(left + 4 if at_left else right - 4, ty - 8 if ty - 8 > top else ty + 18, target_text, anchor="start" if at_left else "end", tone=sk.INK2))
    lines, (end_x, end_y) = _lines(f, x, y)
    parts += lines
    if "at_date" in f:
        parts.append(sk.hollow(x(_day(f["at_date"]["date"])), y(f["at_date"]["value"]), r=4))
    parts.append(sk.point(end_x, end_y, r=5))
    # The end of the line: the reading now, then the status word.
    gx = right + 14
    vy = min(max(end_y + 6, top + 4), bottom - 16)
    parts.append(sk.rule(end_x + 8, end_y, gx - 4, end_y, tone=sk.LINE3))
    parts.append(sk.value(gx, vy, f["current"]["shown"], size=22 if wide else 18))
    parts.append(sk.status_word(gx + 1, vy + 20, b["status"]))
    # Launch and due along the foot, on two rows when they would collide.
    launch, due = f"Launch {f['shipped']}", f"Due {f['bar']['by']}"

    def place(cx: float, text: str) -> tuple[float, str, float, float]:
        """Centred under its line, pushed inside the plot; returns the anchor and the label's extent."""
        w = sk.label_width(text)
        if cx - w / 2 < left:
            return left, "start", left, left + w
        if cx + w / 2 > right:
            return right, "end", right - w, right
        return cx, "middle", cx - w / 2, cx + w / 2

    lx, la, l0, l1 = place(xs, launch)
    dx, da, d0, d1 = place(xb, due)
    apart = l1 + 12 < d0 or d1 + 12 < l0
    parts.append(sk.label(lx, bottom + 32, launch, anchor=la))
    parts.append(sk.label(dx, bottom + (32 if apart else 50), due, anchor=da, tone=sk.INK2))
    aria = (
        f"{b['name']}: {b['metric']} is {f['current']['shown']} on {f['current']['date']}, against a target of "
        f"{f['bar']['shown']} {better_words(f)} by {f['bar']['by']}. {b['status'].capitalize()}."
    )
    return sk.frame("".join(parts), label=aria, height=height, width=width, variant=variant)


def mini(b: dict[str, Any]) -> str:
    """One small multiple: the same picture with no text inside; the panel's own line prints the figures."""
    if b["status"] is None:
        return f'<div class="mini"><span class="mini-h"><span>{e(b["name"])}</span>{status_mark(None)}</span><span class="mini-f">{e(plain(b["not_read"]))}</span></div>'
    f = b["figures"]
    w, h = 240.0, 78.0
    x, y = _scales(f, (3, w - 6), (h - 8, 8), 0.14)
    ty = y(f["bar"]["value"])
    parts = [sk.zone(0, 0, w, ty) if f["bar"]["better"] == "higher" else sk.zone(0, ty, w, h - ty)]
    parts.append(sk.deadline(x(_day(f["bar"]["by"])), 2, h - 2))
    parts.append(sk.target_line(0, w, ty))
    lines, (ex, ey) = _lines(f, x, y)
    parts += lines
    parts.append(sk.point(ex, ey, r=3.5))
    aria = f"{b['name']}: {f['current']['shown']} against a target of {f['bar']['shown']} by {f['bar']['by']}. {b['status'].capitalize()}."
    svg = sk.frame("".join(parts), label=aria, height=h, width=w, variant="one")
    return (
        f'<a class="mini" href="#{e(b["slug"])}"><span class="mini-h"><span>{e(b["name"])}</span>{status_mark(b["status"])}</span>{svg}'
        f'<span class="mini-f"><span><b>{e(f["current"]["shown"])}</b> now</span><span>target {e(f["bar"]["shown"])} by {e(f["bar"]["by"])}</span></span></a>'
    )


def key_cell() -> str:
    """The spare cell of the grid, as a key to the marks. It draws no figure."""
    marks = (
        (sk.line_series([(1, 8), (9, 4), (17, 7), (27, 3)], tone=sk.MUTED), "before launch"),
        (sk.line_series([(1, 9), (14, 6), (27, 2)], tone=sk.INK, width=2), "since launch"),
        (sk.target_line(1, 27, 6), "target"),
        (sk.deadline(14, 1, 11), "due date"),
        (sk.zone(1, 0, 26, 12, tone=sk.LINE2), "target met"),
    )
    rows = "".join(f'<span class="mini-f">{sk.icon(m, width=28, height=12)}{t}</span>' for m, t in marks)
    return f'<div class="mini key">{rows}</div>'


def priority(b: dict[str, Any]) -> tuple[int, str]:
    """Which next step leads the page: stalled first, then watch, then landed; the earliest due within each."""
    return ({"stalled": 0, "watch": 1, "landed": 2}.get(b["status"] or "", 3), b["due"] or "9999")


def next_box(b: dict[str, Any]) -> str:
    return (
        f'<div class="next"><b>What to do next</b><div><p>{e(b["name"])}: {e(plain(b["next_step"]))}</p>'
        f'<span class="who"><span class="o">{e(b["decides"])}</span><span class="d">{e(b["due"])}</span></span></div></div>'
    )


def cost_chip(b: dict[str, Any]) -> str:
    """cost-budget-check's word, cited beside the call in ink. It is a build check, never a status colour."""
    c = b.get("cost")
    return f'<span class="chip" title="cited from {e(c["cited_from"])}">cost {e(c["budget_status"])}</span>' if c else ""


def facts(b: dict[str, Any]) -> str:
    f = b["figures"]
    rows = [("Now", f"<b>{e(f['current']['shown'])}</b> on {e(f['current']['date'])}")]
    rows.append(("Target", f"<b>{e(f['bar']['shown'])}</b> {better_words(f)} by {e(f['bar']['by'])}"))
    if "at_date" in f:
        rows.append(("On the due date", f"{e(f['at_date']['shown'])} on {e(f['at_date']['date'])}"))
    if "move" in f:
        m = f["move"]
        size = "outside its range before launch, which did not vary" if m["flat_baseline"] else f"{abs(m['z']):g} times its usual ups and downs before launch"
        rows.append(("Since launch", f"Launched {e(f['shipped'])}. From an average of {e(m['baseline_shown'])} before launch to {e(m['to_shown'])}: {e(size)}."))
    if "outcome" in f:
        o = f["outcome"]
        rows.append(("The result", f"{e(o['metric'])}, the result it should drive: {o['from']:g} to {o['to']:g} over the same weeks."))
    if b.get("cost"):
        rows.append(("Cost", f"{e(b['cost']['budget_status']).capitalize()}, from the cost check. It never changes the status."))
    body = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in rows)
    own = f'<div class="own"><dt>Next step</dt><dd>{e(plain(b["next_step"]))}<span class="o">{e(b["decides"])}</span><span class="d">due {e(b["due"])}</span></dd></div>'
    return f'<dl class="figs">{body}{own}</dl>'


def caption(b: dict[str, Any]) -> str:
    f = b["figures"]
    side = "above" if f["bar"]["better"] == "higher" else "below"
    return (
        f"Grey is before launch on {f['shipped']}, ink since. The dashed line is the target, {f['bar']['shown']}; "
        f"the shaded side, {side} it, is where the target is met. The upright line is the due date, {f['bar']['by']}."
    )


def readings(b: dict[str, Any]) -> str:
    shipped = b["figures"]["shipped"]
    rows = "".join(
        f'<tr><td class="mo">{e(r["date"])}</td><td class="num">{e(r["shown"])}</td><td>{"before launch" if r["date"] < shipped else "since launch"}</td></tr>'
        for r in b["figures"]["series"]
    )
    return f'<div class="tablewrap readings"><table><tr><th>Date</th><th class="num">Reading</th><th>When</th></tr>{rows}</table></div>'


def bet_section(b: dict[str, Any], n: int, illustrative: bool) -> str:
    meta = f'<div class="meta"><span>Project {n:02d}</span></div>'
    head = f'<div class="head"><h2 id="{e(b["slug"])}">{e(b["name"])}</h2><span class="marks">{cost_chip(b)}{status_mark(b["status"])}</span></div>'
    if b["status"] is None:
        return f'<section class="slide">{meta}{head}<p class="lede">{e(plain(b["not_read"]))}</p></section>'
    pic = sk.figure(chart(b, "wide"), chart(b, "tall"), caption=caption(b), illustrative=illustrative)
    checks = "".join(f"<li>{e(CHECKS.get(fl['code'], plain(fl['text'])))}</li>" for fl in b["flags"]) or "<li>Every check passed.</li>"
    fold = (
        f"<details><summary>Checks and readings ({plural(len(b['flags']), 'check')}, {plural(len(b['figures']['series']), 'reading')})</summary>"
        f'<ul class="checks">{checks}</ul>{readings(b)}<p class="mini-f">Source: {e(b["source"])}</p></details>'
    )
    return f'<section class="slide">{meta}{head}<p class="lede">{e(b["metric"])}. {e(plain(b["reason"]))}</p><div class="cols"><div>{pic}{fold}</div>{facts(b)}</div></section>'


def engineers(result: dict[str, Any]) -> str:
    """Flag codes, files and the record key, folded: none of it is needed to act on the read."""
    rows = []
    for b in result["bets"]:
        codes = "".join(f'<span class="chip">{e(fl["code"])}</span>' for fl in b["flags"]) or "none"
        brief = Path(b["brief_path"]).name if b.get("brief_path") else "none"
        rows.append(f"<tr><td>{e(b['name'])}</td><td>{e(b['status'] or 'not read')}</td><td>{codes}</td><td>{e(brief)}</td><td>{e(b['slug'])}</td></tr>")
    head = "<tr><th>Project</th><th>Status</th><th>Flag codes</th><th>Landing brief</th><th>Slug</th></tr>"
    note = (
        '<p class="mini-f">With --loop and --bet, the read adds its page to the project file: the <code>landed</code> key of '
        "<code>landing/&lt;slug&gt;.json</code>, and no other key. Cost is cited from the <code>cost</code> key that "
        "cost-budget-check wrote; it is never recomputed. "
        f"Built by {e(result.get('computed_by', 'did-it-land'))}.</p>"
    )
    return (
        '<section class="slide"><div class="meta"><span>Detail</span></div>'
        f'<details><summary>For your engineers</summary><div class="tablewrap eng"><table>{head}{"".join(rows)}</table></div>{note}</details></section>'
    )


def page(result: dict[str, Any]) -> str:
    company = result["company"]
    title = f"Did it land? {company}" if company else "Did it land?"
    read = [b for b in result["bets"] if b["status"]]
    n = len(result["bets"])
    lede = (
        f"{count_word(n)} project{'s' if n != 1 else ''}, each a piece of work you expect to move a number. Each is read against the target and "
        "date set in its <b>landing brief</b>, a one-page plan written before work started: what good looks like, by when, at what cost."
    )
    minis = sk.figure(
        f'<div class="minis">{"".join(mini(b) for b in result["bets"])}{key_cell() if len(result["bets"]) % 4 else ""}</div>',
        caption="Each line is one project's number. Grey is before launch, ink since. The dashed line is its target, "
        "the upright line its due date, and the shaded side is where the target is met.",
        illustrative=result["illustrative"],
    )
    lead = next_box(min(read, key=priority)) if read else ""
    version = "v" + result.get("computed_by", "did-it-land ?").rsplit(" ", 1)[-1]
    header = sk.page_header("Did it land?", date=f"Read {result['as_of'][:10]}", version=version, illustrative=result["illustrative"])
    sections = "".join(bet_section(b, i, result["illustrative"]) for i, b in enumerate(result["bets"], start=1))
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{floor_fonts(stylesheet() + sk.CSS + PAGE_CSS)}</style></head><body><main class="solo">'
        f'<section class="slide cover">{header}<h1>{e(verdict(result))}</h1><p class="lede">{lede}</p>{minis}{lead}</section>'
        f"{sections}{engineers(result)}"
        '<p class="foot">A number moving is not proof that the project moved it. This read says whether the number reached the target, not why. '
        "Every figure is computed in code from the sources named.</p></main></body></html>\n"
    )
