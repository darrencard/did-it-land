"""The read as one self-contained HTML page, in the Leader Report style guide and the Landing Loop's one visual family.

The page uses the report's own stylesheet, taken whole from its template (assets/vendor/template.html, vendored
byte-identical at a pinned commit), and draws its pictures with svgkit (scripts/vendor/svgkit.py, vendored
byte-identical from landing-loop). Only a few rules for this page's layout are added.

The page reads top down for someone who has never seen the loop: the shared header, the verdict as the heading,
the scorecard (one row per project: name, range line, `before → now · TARGET x`, status word), then one thing to do
next. Each project's detail follows; the one this read is about is open, the others fold. Checks and readings sit
in a fold, and flag codes, file names and the record key sit in a last fold for engineers. Public copy uses plain
words: project, target, inside normal ups and downs.

The scorecard follows the scorecard grammar (svgkit 1.2.0, one scale per frame): HTML rows split by hairlines, Geist Mono 12px for
labels, figures and words, Geist 14px for names, and a fixed-height range line with no text in it.

Colour means one thing each: green and red only for the words landed and stalled and the dot in the same row, brass
for the person who decides, grey for the average before launch. The target is a tick, never a green band.
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

# Layout for this page only. Everything else comes from the template's stylesheet and svgkit.CSS.
PAGE_CSS = """
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{min-height:0;padding-top:40px;padding-bottom:48px;justify-content:flex-start}
.solo h1{font-size:clamp(34px,4.6vw,60px);line-height:1;letter-spacing:-.04em;max-width:22ch;margin-bottom:20px}
.solo .lede{margin-bottom:28px}
.solo .lede b{color:var(--t1);font-weight:500}
.next{margin-top:28px;display:grid;grid-template-columns:200px minmax(0,1fr);gap:8px 32px;align-items:baseline;border:1px solid var(--brass);border-radius:12px;padding:20px 24px;background:var(--brass-bg)}
.next>b{font:400 11px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--brass)}
.next p{margin:0;font-size:16px;line-height:1.5;color:var(--t1)}
.next .who{display:flex;flex-wrap:wrap;gap:4px 24px;margin-top:10px;font:400 11.5px/16px var(--mono);color:var(--brass)}
.next .who span::before{font-size:11px;letter-spacing:.1em;color:var(--t3);margin-right:8px}
.next .who .o::before{content:"DECIDES"}.next .who .d::before{content:"DUE"}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:10px 24px}
.head h2{margin-bottom:12px}
.proj .marks{display:flex;align-items:baseline;gap:12px}
.proj .marks .sc-w{font:400 12px/16px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--t2)}
.solo .scg{margin-top:8px}
.figs{margin:0;display:grid;max-width:760px}
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
.src{font:400 12px/16px var(--mono);color:var(--t3)}
.readings td,.readings th{padding:7px 14px}
.eng td{font-size:12px}
.eng code{margin-right:6px}
.proj>summary{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;font-weight:400}
.proj>summary h2{margin:0}
.proj[open]>summary{margin-bottom:16px}
.solo details.proj{margin-top:0;border-top:0;padding:0}
::selection{background:var(--t1);color:var(--bg)}
:focus-visible{outline-color:var(--t1)}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:24px}.next{grid-template-columns:1fr}}
@media (max-width:560px){.figs>div{grid-template-columns:1fr;gap:0}}
"""

NUMBER_WORDS = ("No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve")

# A held call, in plain words. The codes themselves print only in the engineers' fold.
HELD = {
    "within-noise": "inside normal ups and downs",
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
    "within-noise": "Inside normal ups and downs: since launch the number sits inside the ups and downs it had before launch.",
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
        lead = "" if why == ["inside normal ups and downs"] else "not called yet: "
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


NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")


def decimals(shown: str) -> int:
    """How many decimals a printed value carries: "43%" 0, "18.1%" 1."""
    m = NUMBER.search(shown)
    return len(m.group().split(".")[1]) if m and "." in m.group() else 0


def prior_shown(f: dict[str, Any]) -> str | None:
    """The average before launch, to as many decimals as the actual prints, in its own form: 21.67% beside 43%
    reads 22%, 16.92% beside 18.1% reads 16.9%. None when there is no move to show."""
    m = f.get("move")
    if not m:
        return None
    value = f"{m['baseline_mean']:,.{decimals(f['current']['shown'])}f}"
    return NUMBER.sub(lambda _: value, m["baseline_shown"], count=1)


# Why a watch row past its target is held, in the flag's own plain words, as the second line under the status word.
PAST = {
    "within-noise": "inside normal ups and downs",
    "source-stale": "data out of date",
    "source-jumpy": "data jumped",
    "metric-up-outcome-down": "outcome fell",
    "metric-up-outcome-flat": "outcome held flat",
    "brief-changed": "plan changed",
    "brief-after-launch": "target set after launch",
    "no-baseline": "no readings before launch",
}


def past_target(b: dict[str, Any]) -> str:
    """"past target · outcome fell" for a watch row whose call is held past its target; else ""."""
    if b["status"] != "watch" or "the call is held" not in b["reason"]:
        return ""
    why = [PAST[fl["code"]] for fl in b["flags"] if fl["code"] in PAST]
    return " · ".join(["past target", *dict.fromkeys(why)])


def figure_tail(f: dict[str, Any]) -> str:
    """"LOWER IS BETTER" on the figure line of a metric that should fall; else ""."""
    return "LOWER IS BETTER" if f["bar"]["better"] == "lower" else ""


def scorecard_row(b: dict[str, Any], domain: tuple[float, float]) -> str:
    """One project: name | range line | before launch → now · TARGET x | status word, and the cost word when set.
    Every row shares the frame's one scale, each value read as a share of its own target, so the ticks line up."""
    if b["status"] is None:
        return sk.sc_row(b["name"], figure=sk.figure_line("NO READING"), word=sk.check_word("not read"))
    f = b["figures"]
    m = f.get("move")
    picture = sk.range_line(
        prior=m["baseline_mean"] if m else None, actual=f["current"]["value"], target=f["bar"]["value"], status=b["status"], domain=domain, relative=True
    )
    figure = sk.figure_line(f["current"]["shown"], prior=prior_shown(f), target=f["bar"]["shown"], tail=figure_tail(f))
    why = past_target(b)
    word = sk.status_mark(b["status"]) + (sk.check_word(why) if why else "") + cost_word(b)
    return sk.sc_row(b["name"], picture=picture, figure=figure, word=word)


def scorecard(result: dict[str, Any]) -> str:
    """Every project as one row of the scorecard, in the grammar of the /update outcome scorecard."""
    read = [b for b in result["bets"] if b["status"]]
    domain = sk.frame_domain(
        [(b["figures"]["move"]["baseline_mean"] if "move" in b["figures"] else None, b["figures"]["current"]["value"], b["figures"]["bar"]["value"]) for b in read]
    )
    key = sk.legend("prior", "average before launch") + sk.legend("target", "target")
    return sk.sc_frame(
        [scorecard_row(b, domain) for b in result["bets"]],
        label=verdict(result),
        title="Scorecard",
        head=["Project", "", "Before → now · target", "Status"],
        legend=key,
        caption="Each row is one project's number against its own target, so the target ticks line up: the grey dot is its average before launch, the coloured dot the latest reading.",
        illustrative=result["illustrative"],
    )


def priority(b: dict[str, Any]) -> tuple[int, str]:
    """Which next step leads the page: stalled first, then watch, then landed; the earliest due within each."""
    return ({"stalled": 0, "watch": 1, "landed": 2}.get(b["status"] or "", 3), b["due"] or "9999")


def next_box(b: dict[str, Any]) -> str:
    return (
        f'<div class="next"><b>What to do next</b><div><p>{e(b["name"])}: {e(plain(b["next_step"]))}</p>'
        f'<span class="who"><span class="o">{e(b["decides"])}</span><span class="d">{e(b["due"])}</span></span></div></div>'
    )


def cost_word(b: dict[str, Any]) -> str:
    """cost-budget-check's word, cited as text beside the call. It is a build check, never a status colour."""
    c = b.get("cost")
    return sk.check_word(f"cost {c['budget_status']}") if c else ""


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


def readings(b: dict[str, Any]) -> str:
    shipped = b["figures"]["shipped"]
    rows = "".join(
        f'<tr><td class="mo">{e(r["date"])}</td><td class="num">{e(r["shown"])}</td><td>{"before launch" if r["date"] < shipped else "since launch"}</td></tr>'
        for r in b["figures"]["series"]
    )
    return f'<div class="tablewrap readings"><table><tr><th>Date</th><th class="num">Reading</th><th>When</th></tr>{rows}</table></div>'


def bet_section(b: dict[str, Any], n: int, open_: bool) -> str:
    """One project's detail. Only the project this read is about opens; the others fold, and their rows stay on the scorecard."""
    meta = f'<div class="meta"><span>Project {n:02d}</span></div>'
    summary = f'<summary><h2 id="{e(b["slug"])}">{e(b["name"])}</h2><span class="marks">{status_mark(b["status"])}{cost_word(b)}</span></summary>'
    if b["status"] is None:
        body = f'<p class="lede">{e(plain(b["not_read"]))}</p>'
    else:
        checks = "".join(f"<li>{e(CHECKS.get(fl['code'], plain(fl['text'])))}</li>" for fl in b["flags"]) or "<li>Every check passed.</li>"
        fold = (
            f"<details><summary>Checks and readings ({plural(len(b['flags']), 'check')}, {plural(len(b['figures']['series']), 'reading')})</summary>"
            f'<ul class="checks">{checks}</ul>{readings(b)}<p class="src">Source: {e(b["source"])}</p></details>'
        )
        body = f'<p class="lede">{e(b["metric"])}. {e(plain(b["reason"]))}</p>{facts(b)}{fold}'
    return f'<section class="slide">{meta}<details class="proj"{" open" if open_ else ""}>{summary}{body}</details></section>'


def engineers(result: dict[str, Any]) -> str:
    """Flag codes, files and the record key, folded: none of it is needed to act on the read."""
    rows = []
    for b in result["bets"]:
        codes = "".join(f'<code>{e(fl["code"])}</code>' for fl in b["flags"]) or "none"
        brief = Path(b["brief_path"]).name if b.get("brief_path") else "none"
        rows.append(f"<tr><td>{e(b['name'])}</td><td>{e(b['status'] or 'not read')}</td><td>{codes}</td><td>{e(brief)}</td><td>{e(b['slug'])}</td></tr>")
    head = "<tr><th>Project</th><th>Status</th><th>Flag codes</th><th>Landing brief</th><th>Slug</th></tr>"
    note = (
        '<p class="src">With --loop and --bet, the read adds its page to the project file: the <code>landed</code> key of '
        "<code>landing/&lt;slug&gt;.json</code>, and no other key. Cost is cited from the <code>cost</code> key that "
        "cost-budget-check wrote; it is never recomputed. "
        f"Built by {e(result.get('computed_by', 'did-it-land'))}.</p>"
    )
    return (
        '<section class="slide"><div class="meta"><span>Detail</span></div>'
        f'<details><summary>For your engineers</summary><div class="tablewrap eng"><table>{head}{"".join(rows)}</table></div>{note}</details></section>'
    )


def page(result: dict[str, Any], focus: str | None = None) -> str:
    """The page. focus is the slug of the project this read is about (the --bet one); it defaults to the first."""
    company = result["company"]
    title = f"Did it land? {company}" if company else "Did it land?"
    read = [b for b in result["bets"] if b["status"]]
    n = len(result["bets"])
    lede = (
        f"{count_word(n)} project{'s' if n != 1 else ''}, each a piece of work you expect to move a number. Each is read against the target and "
        "date set in its <b>landing brief</b>, a one-page plan written before work started: what good looks like, by when, at what cost."
    )
    lead = next_box(min(read, key=priority)) if read else ""
    version = "v" + result.get("computed_by", "did-it-land ?").rsplit(" ", 1)[-1]
    header = sk.page_header("Did it land?", date=f"Read {result['as_of'][:10]}", version=version, illustrative=result["illustrative"])
    focus = focus or (result["bets"][0]["slug"] if result["bets"] else None)
    sections = "".join(bet_section(b, i, b["slug"] == focus) for i, b in enumerate(result["bets"], start=1))
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{floor_fonts(stylesheet() + sk.CSS + sk.SCORECARD_CSS + PAGE_CSS)}</style></head><body><main class="solo">'
        f'<section class="slide cover">{header}<h1>{e(verdict(result))}</h1><p class="lede">{lede}</p>{scorecard(result)}{lead}</section>'
        f"{sections}{engineers(result)}"
        '<p class="foot">A number moving is not proof that the project moved it. This read says whether the number reached the target, not why. '
        "Every figure is computed in code from the sources named.</p></main></body></html>\n"
    )
