"""The read as one self-contained HTML page, in the Leader Report style guide.

The page uses the report's own stylesheet, taken whole from its template (assets/vendor/template.html, vendored
byte-identical at a pinned commit), so it is the same brand family as the deck: the same fonts, tokens, status
marks, scorecard rows and bullet range line. Only a few rules for this page's layout are added. It follows the
report's references/design.md: mono capitals for labels, sans for sentences; hairlines, not boxes; green,
grey-white and red for status only, with the word always printed; brass for a person's call; grey for the
baseline and ink for the actual; one line per figure, `baseline -> actual . BAR x`.

Nothing is loaded from the network, nothing in the output depends on the clock or the machine, and every piece
of text from a source is escaped.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
STYLE = re.compile(r"<style>(.*?)</style>", re.S)

# Layout for this page only. Everything else comes from the template's stylesheet.
PAGE_CSS = """
main.solo{margin-left:0}
.solo .slide{min-height:0}
.solo .slide.cover{padding-top:72px;padding-bottom:40px}
.solo .lede{margin-bottom:8px}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:10px 24px}
.head h2{margin-bottom:12px}
.rows{margin-top:8px}
.rows>div{display:grid;grid-template-columns:168px minmax(0,1fr);gap:6px 36px;border-top:1px solid var(--line);padding:14px 0}
.rows>div>span:first-child{font:400 10px/22px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.rows>div>span:last-child{color:var(--t2);font-size:13.5px}
.rows .chip{font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t2);
border:1px solid var(--line2);border-radius:3px;padding:1px 6px;margin-right:10px;white-space:nowrap}
.solo .need{margin-top:24px}
.solo .need-r{margin-top:0}
.sc-n .sc-d{max-width:46ch}
.foot{max-width:1120px;margin:0 auto;padding:28px 40px 64px;color:var(--t3);font-size:12px}
@media (max-width:980px){.rows>div{grid-template-columns:1fr;gap:2px}.foot{padding:24px 16px 48px}.solo .slide.cover{padding-top:48px}}
"""

MARK = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">'
    '<rect x="2" y="13" width="3" height="7" fill="var(--agent)"/><rect x="7" y="10" width="3" height="10" fill="var(--agent)"/>'
    '<rect x="12" y="2" width="1.5" height="20" fill="var(--brass)"/><rect x="16" y="4" width="4" height="16" fill="var(--t1)"/></svg>'
)


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


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


def _pct(v: float) -> str:
    return f"{round(v, 1):g}"


def bullet(b: dict[str, Any]) -> str:
    """Baseline, actual and the bar on one line, as the report's render.bullet() draws a scorecard row.

    Grey dot: the pre-launch mean. Status dot: the reading now. Green band: the healthy side of the bar.
    Scaled from zero to 1.18 times the largest of the three. Drawn only when all three exist.
    """
    f = b["figures"]
    if "move" not in f:
        return ""
    prior, actual, bar = f["move"]["baseline_mean"], f["current"]["value"], f["bar"]["value"]
    top = max(prior, actual, bar) * 1.18 or 1

    def x(v: float) -> float:
        return max(0.0, min(v / top, 1)) * 100

    t = x(bar)
    band = f'<i class="ok" style="left:0;width:{_pct(t)}%"></i>' if f["bar"]["better"] == "lower" else f'<i class="ok" style="left:{_pct(t)}%;right:0"></i>'
    lo, hi = sorted((x(prior), x(actual)))
    return (
        f'<span class="bl" aria-hidden="true"><i class="tr"></i>{band}<i class="mv" style="left:{_pct(lo)}%;width:{_pct(hi - lo)}%"></i>'
        f'<i class="pr" style="left:{_pct(x(prior))}%"></i><i class="ac {e(b["status"])}" style="left:{_pct(x(actual))}%"></i></span>'
    )


def line(b: dict[str, Any]) -> str:
    """`baseline -> actual . BAR x`, in mono, the actual in ink."""
    f = b["figures"]
    base = f"{e(f['move']['baseline_shown'])} <i>&rarr;</i> " if "move" in f else ""
    return f'<span class="sc-l">{base}<b>{e(f["current"]["shown"])}</b> &middot; <em>Bar</em> {e(f["bar"]["shown"])} <em>by</em> {e(f["bar"]["by"])}</span>'


def scorecard(result: dict[str, Any]) -> str:
    rows = []
    for b in result["bets"]:
        if b["status"] is None:
            rows.append(
                f'<div class="sc-r"><div class="sc-n"><span>{e(b["name"])}</span><span class="sc-d">{e(b["not_read"])}</span></div>'
                f'<div class="sc-v"></div><div class="sc-s">{status_mark(None)}</div></div>'
            )
            continue
        rows.append(
            f'<div class="sc-r"><div class="sc-n"><span><a href="#{e(b["slug"])}">{e(b["name"])}</a></span><span class="sc-d">{e(b["metric"])}</span></div>'
            f'<div class="sc-v">{bullet(b)}{line(b)}</div><div class="sc-s">{status_mark(b["status"])}</div></div>'
        )
    head = '<div class="sc-h"><span>Bet and metric</span><span>Baseline &rarr; now &middot; bar</span><span>Status</span></div>'
    return f'<div class="tablewrap sc">{head}{"".join(rows)}</div>'


def bet_section(b: dict[str, Any], n: int) -> str:
    meta = f'<div class="meta"><span>Bet {n:02d}</span><span>{e(b["id"])}</span></div>'
    head = f'<div class="head"><h2 id="{e(b["slug"])}">{e(b["name"])}</h2>{status_mark(b["status"])}</div>'
    if b["status"] is None:
        return f'<section class="slide">{meta}{head}<p class="lede">{e(b["not_read"])}</p></section>'
    f = b["figures"]
    rows = [("Now", f"{f['current']['shown']} on {f['current']['date']}. Source: {b['source']}.")]
    rows.append(("Bar", f"{f['bar']['shown']}, {f['bar']['better']} is better, by {f['bar']['by']}."))
    if "at_date" in f:
        rows.append(("At the date", f"{f['at_date']['shown']} on {f['at_date']['date']}."))
    if "move" in f:
        m = f["move"]
        size = "outside it (the baseline was flat)" if m["flat_baseline"] else f"{abs(m['z']):g} times the pre-launch spread ({m['baseline_sd']:g})"
        rows.append(("Since launch", f"Shipped {f['shipped']}. Pre-launch mean {m['baseline_shown']} over {m['baseline_n']} readings, then {m['to_shown']}: {size}."))
    if "outcome" in f:
        o = f["outcome"]
        rows.append(("Outcome", f"{o['metric']}: {o['from']:g} to {o['to']:g} over the same window ({o['n']} readings). Source: {o['source']}."))
    for key, figs in b["context"].items():
        rows.append((f"Loop: {key}", "; ".join(f"{c['name']} {c['value']:,.10g}{' ' + c['unit'] if c['unit'] else ''} ({c['source']})" for c in figs) + "."))
    body = "".join(f"<div><span>{e(k)}</span><span>{e(v)}</span></div>" for k, v in rows)
    flags = "".join(f'<div><span>Flag</span><span><span class="chip">{e(fl["code"])}</span>{e(fl["text"])}</span></div>' for fl in b["flags"])
    call = (
        f'<div class="need"><b>Next step</b><div class="need-r"><p>{e(b["next_step"])}</p>'
        f'<span class="mono" style="color:var(--brass);font-size:11px">{e(b["decides"])}</span>'
        f'<span class="mono t3" style="font-size:11px">by {e(f["bar"]["by"])}</span></div></div>'
    )
    return f'<section class="slide">{meta}{head}<p class="lede">{e(b["reason"])}</p><div class="rows">{body}{flags}</div>{call}</section>'


def page(result: dict[str, Any]) -> str:
    c = result["counts"]
    company = result["company"]
    title = f"Did it land? {company}" if company else "Did it land?"
    meta = [f"Read {result['as_of'][:10]}", result.get("computed_by", "did-it-land")]
    meta_html = "".join(f"<span>{e(m)}</span>" for m in meta)
    if result["illustrative"]:
        meta_html += '<span class="ill">Illustrative</span>'
    lede = f"{c['landed']} landed, {c['watch']} watch, {c['stalled']} stalled" + (f", {c['not read']} not read." if c["not read"] else ".")
    lede += " Each bet is read against the bar and date its landing brief set before work started."
    sections = "".join(bet_section(b, i) for i, b in enumerate(result["bets"], start=1))
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><style>{stylesheet()}{PAGE_CSS}</style></head><body><main class="solo">'
        f'<section class="slide cover"><div class="brand">{MARK}<span translate="no">DACARD</span></div><div class="meta">{meta_html}</div>'
        f'<h1>{e(title)}</h1><p class="lede">{e(lede)}</p></section>'
        f'<section class="slide"><div class="meta"><span>Scorecard</span></div><h2>Every bet, against its bar</h2>{scorecard(result)}</section>'
        f"{sections}"
        '<p class="foot">A metric moving is not proof that the bet moved it. This read says whether the metric reached the bar, not why. '
        "Every figure is computed in code from the sources named.</p></main></body></html>\n"
    )
