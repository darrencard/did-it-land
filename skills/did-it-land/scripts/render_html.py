"""The read as one self-contained HTML page, in the Leader Report style guide.

Rules followed from the report's references/design.md: mono capitals for labels, sans for sentences; hairlines,
not boxes; green, grey-white and red for status only, with the word always printed; brass for a person's call;
grey for the plan (the baseline) and ink for the actual; one line per figure, `baseline -> actual . BAR x`.
The fonts are taken from the report's own template (assets/vendor/template.html, vendored at a pinned commit),
so the page needs nothing from the network. Every piece of text from a source is escaped.

Standard library only. Python 3.11 or later.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "vendor" / "template.html"
FONT_FACE = re.compile(r"@font-face\{[^}]*\}")

CSS = """
:root{color-scheme:dark;--bg:#0A0A0A;--band:#111111;--s1:#121212;--s3:#1D1D1B;
--line:rgba(242,242,239,.08);--line2:rgba(242,242,239,.15);--line3:rgba(242,242,239,.24);
--t1:#F2F2EF;--t2:#B9B9B4;--t3:#97968F;--brass:#E3A948;--brass-bg:rgba(227,169,72,.08);
--agent:#8F8B83;--agent-mid:#6E6A62;--landed:#5CD38C;--watch:#D6D6D1;--stalled:#F0654F;
--sans:"Geist",system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--display:"Instrument Sans","Geist",system-ui,sans-serif;--mono:"Geist Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--t1);font-family:var(--sans);font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
main{max-width:1120px;margin:0 auto;padding:48px 40px 64px}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;font-size:15px;letter-spacing:-.01em}
.lab,.meta,th,.code,.when{font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--t3)}
.meta{display:flex;flex-wrap:wrap;gap:8px 14px;margin:20px 0 18px}
.ill{color:var(--t2);background:var(--s3);border-radius:4px;padding:0 7px}
h1{font-family:var(--display);font-weight:600;font-size:clamp(40px,5.6vw,72px);font-stretch:88%;line-height:.95;letter-spacing:-.05em;margin:0 0 20px}
h2{font-family:var(--display);font-weight:600;font-size:clamp(22px,2.4vw,30px);font-stretch:90%;letter-spacing:-.035em;line-height:1.1;margin:0 0 6px}
.lede{font-size:clamp(16px,1.5vw,19px);color:var(--t2);max-width:62ch;margin:0 0 36px}
.st{display:inline-flex;align-items:center;gap:7px;font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;white-space:nowrap}
.st::before{content:"";width:7px;height:7px;border-radius:2px;background:currentColor;flex:none}
.st.watch::before{width:8px;height:8px;border-radius:50%;background:none;border:1.5px solid currentColor}
.st.landed{color:var(--landed)}.st.watch{color:var(--watch)}.st.stalled{color:var(--stalled)}.st.none{color:var(--t3)}
.st.none::before{background:none;border:1.5px dashed currentColor;border-radius:50%}
.frame{border:1px solid var(--line);border-radius:12px;background:var(--s1);overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;padding:14px 18px 12px;border-bottom:1px solid var(--line2);white-space:nowrap}
td{padding:14px 18px;border-bottom:1px solid var(--line);vertical-align:middle;color:var(--t2)}
tr:last-child td{border-bottom:0} td:first-child{color:var(--t1)}
.fig{font:400 11.5px var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.fig b{color:var(--t1);font-weight:400}
.rl{position:relative;height:14px;min-width:140px}
.rl .ln{position:absolute;left:0;right:0;top:6px;height:1px;background:var(--line3)}
.rl .d{position:absolute;top:3px;width:8px;height:8px;border-radius:50%;margin-left:-4px}
.rl .d.p{background:var(--agent-mid)} .rl .d.a.landed{background:var(--landed)} .rl .d.a.watch{background:var(--watch)} .rl .d.a.stalled{background:var(--stalled)}
.rl .tk{position:absolute;top:0;width:1px;height:14px;background:var(--t1)}
section.bet{border-top:1px solid var(--line2);padding:32px 0 8px;margin-top:40px}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px 24px;align-items:baseline;margin-bottom:14px}
.reason{color:var(--t2);max-width:72ch;margin:0 0 18px}
.rows>div{display:grid;grid-template-columns:180px minmax(0,1fr);gap:8px 32px;border-top:1px solid var(--line);padding:12px 0}
.rows>div>span:last-child{color:var(--t2)}
.code{color:var(--t2);border:1px solid var(--line2);border-radius:3px;padding:0 5px;margin-right:8px;white-space:nowrap}
.call{border:1px dashed var(--brass);border-radius:10px;padding:14px 18px;background:var(--brass-bg);margin-top:18px;
display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 32px}
.call .who{color:var(--brass);font:400 10px/16px var(--mono);letter-spacing:.1em;text-transform:uppercase;white-space:nowrap}
.call p{margin:0;color:var(--t2)}
.not{color:var(--t3)}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);color:var(--t3);font-size:12px}
@media (max-width:760px){main{padding:32px 16px 48px}.pic{display:none}.rows>div,.call{grid-template-columns:1fr}.rl{min-width:96px}}
@media print{:root{color-scheme:light;--bg:#fff;--s1:#fff;--s3:#eee;--t1:#111;--t2:#333;--t3:#555;--line:#ddd;--line2:#ccc;--line3:#bbb;--watch:#666}}
"""

MARK = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">'
    '<rect x="2" y="13" width="3" height="7" fill="var(--agent)"/><rect x="7" y="10" width="3" height="10" fill="var(--agent)"/>'
    '<rect x="12" y="2" width="1.5" height="20" fill="var(--brass)"/><rect x="16" y="4" width="4" height="16" fill="var(--t1)"/></svg>'
)


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def fonts() -> str:
    """The three @font-face rules from the report's template, so the page carries its own fonts."""
    try:
        return "".join(FONT_FACE.findall(TEMPLATE.read_text(encoding="utf-8")))
    except OSError:
        return ""  # the page still renders in system fonts


def status_mark(status: str | None) -> str:
    word = status or "not read"
    cls = status or "none"
    return f'<span class="st {e(cls)}">{e(word)}</span>'


def range_line(b: dict[str, Any]) -> str:
    """Baseline (grey dot), actual (status dot) and the bar (a tick), on one line. Draws only when all three exist."""
    f = b["figures"]
    if "move" not in f:
        return ""
    base, actual, bar = f["move"]["baseline_mean"], f["current"]["value"], f["bar"]["value"]
    lo, hi = min(base, actual, bar), max(base, actual, bar)
    span = (hi - lo) or 1
    pad = span * 0.08

    def pos(v: float) -> str:
        return f"{(v - lo + pad) / (span + 2 * pad) * 100:.1f}%"

    label = f"Baseline {f['move']['baseline_shown']}, now {f['current']['shown']}, bar {f['bar']['shown']}"
    return (
        f'<div class="rl" role="img" aria-label="{e(label)}"><span class="ln"></span>'
        f'<span class="tk" style="left:{pos(bar)}"></span><span class="d p" style="left:{pos(base)}"></span>'
        f'<span class="d a {e(b["status"])}" style="left:{pos(actual)}"></span></div>'
    )


def figure_line(b: dict[str, Any]) -> str:
    f = b["figures"]
    base = f"{e(f['move']['baseline_shown'])} &rarr; " if "move" in f else ""
    return f'<span class="fig">{base}<b>{e(f["current"]["shown"])}</b> &middot; BAR {e(f["bar"]["shown"])}</span>'


def scorecard(result: dict[str, Any]) -> str:
    rows = []
    for b in result["bets"]:
        if b["status"] is None:
            rows.append(f'<tr><td>{e(b["name"])}</td><td class="not" colspan="2">{e(b["not_read"])}</td><td class="pic"></td><td>{status_mark(None)}</td></tr>')
            continue
        rows.append(f'<tr><td>{e(b["name"])}</td><td>{e(b["metric"])}</td><td>{figure_line(b)}</td><td class="pic">{range_line(b)}</td><td>{status_mark(b["status"])}</td></tr>')
    cols = ["Bet", "Metric", "Baseline &rarr; now &middot; bar"]
    head = "<tr>" + "".join(f'<th scope="col">{c}</th>' for c in cols) + '<th scope="col" class="pic">Picture</th><th scope="col">Status</th></tr>'
    return f'<div class="frame"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def bet_section(b: dict[str, Any]) -> str:
    head = f'<div class="head"><h2 id="{e(b["slug"])}">{e(b["name"])}</h2>{status_mark(b["status"])}</div>'
    if b["status"] is None:
        return f'<section class="bet">{head}<p class="reason">{e(b["not_read"])}</p></section>'
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
    body = "".join(f'<div><span class="lab">{e(k)}</span><span>{e(v)}</span></div>' for k, v in rows)
    flags = "".join(f'<div><span class="lab">Flag</span><span><span class="code">{e(fl["code"])}</span>{e(fl["text"])}</span></div>' for fl in b["flags"])
    call = f'<div class="call"><p>{e(b["next_step"])}</p><span class="who">Decides: {e(b["decides"])}</span></div>'
    return f'<section class="bet">{head}<p class="reason">{e(b["reason"])}</p><div class="rows">{body}{flags}</div>{call}</section>'


def page(result: dict[str, Any]) -> str:
    c = result["counts"]
    company = result["company"]
    title = f"Did it land? {company}" if company else "Did it land?"
    meta = [f"Read {result['as_of'][:10]}", result.get("computed_by", "did-it-land")]
    meta_html = "".join(f"<span>{e(m)}</span>" for m in meta)
    if result["illustrative"]:
        meta_html += '<span class="ill">Illustrative: sample data</span>'
    lede = f"{c['landed']} landed, {c['watch']} watch, {c['stalled']} stalled, {c['not read']} not read."
    sections = "".join(bet_section(b) for b in result["bets"])
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{e(title)}</title><style>{fonts()}{CSS}</style></head><body><main>"
        f'<div class="brand">{MARK}<span translate="no">DACARD</span></div><div class="meta">{meta_html}</div>'
        f'<h1>{e(title)}</h1><p class="lede">{e(lede)}</p>{scorecard(result)}{sections}'
        "<footer>A metric moving is not proof that the bet moved it. This read says whether the metric reached the bar, not why. "
        "Every figure is computed in code from the sources named.</footer></main></body></html>\n"
    )
