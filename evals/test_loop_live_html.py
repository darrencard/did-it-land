"""v0.2: the Landing Loop record, live data through the vendored collectors, the HTML page, and the pins."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import FIXTURE, SCRIPTS

# isort: split
import did_it_land
import from_run
import loop
import render_html
import svgkit

SKILL = SCRIPTS.parent
LIVE = FIXTURE.parent.parent / "live"


def copy_fixture(d: Path) -> Path:
    shutil.copytree(FIXTURE.parent, d / "acme")
    return d / "acme" / "bundle.json"


class Pins(unittest.TestCase):
    def test_vendored_files_match_their_pinned_hashes(self):
        manifest = json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["commit"], r"^[0-9a-f]{40}$")
        for rel, info in manifest["files"].items():
            digest = hashlib.sha256((SKILL / rel).read_bytes()).hexdigest()
            self.assertEqual(digest, info["sha256"], f"{rel} changed. Copy it again from the pinned commit and update VENDORED.json.")

    def test_svgkit_matches_its_landing_loop_pin(self):
        pin = json.loads((SKILL / "VENDORED.json").read_text(encoding="utf-8"))["landing-loop"]
        self.assertRegex(pin["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(set(pin["files"]), {"scripts/vendor/svgkit.py"})
        for rel, info in pin["files"].items():
            digest = hashlib.sha256((SKILL / rel).read_bytes()).hexdigest()
            self.assertEqual(digest, info["sha256"], f"{rel} changed. Copy it again from landing-loop at the pinned commit and update VENDORED.json.")

    def test_brief_parser_is_the_one_the_loop_shares(self):
        # The same hash spec-auditor pins, so every skill in the loop reads the brief the same way.
        digest = hashlib.sha256((SCRIPTS / "landing_brief.py").read_bytes()).hexdigest()
        self.assertEqual(digest, "2d13573543c74ebe1bf001b97287287474a0ec298f34709a1bbfc643be051948")


class LoopRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.bundle = copy_fixture(self.d)
        self.work = self.d / "work"

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, slug):
        return json.loads(loop.path_for(self.work, slug).read_text(encoding="utf-8"))

    def run_read(self):
        result = did_it_land.read(self.bundle, self.work)
        did_it_land.write_loop(result, self.work)
        return result

    def test_new_records_for_read_bets_only(self):
        self.run_read()
        names = sorted(p.stem for p in (self.work / "landing").glob("*.json"))
        self.assertEqual(len(names), 7)
        self.assertNotIn("customer-portal-redesign", names)
        r = self.record("quote-drafting-assistant")
        self.assertEqual(r["schema"], "landing-loop/1")
        self.assertEqual(r["landed"]["status"], "landed")
        self.assertEqual(len(r["brief"]["sha256"]), 64)

    def test_every_figure_has_the_loop_shape(self):
        self.run_read()
        for p in (self.work / "landing").glob("*.json"):
            for name, f in json.loads(p.read_text(encoding="utf-8"))["landed"]["figures"].items():
                self.assertEqual(set(f), {"value", "unit", "source", "window", "as_of"}, f"{p.name} {name}")
                self.assertTrue(f["source"], f"{p.name} {name}")
                self.assertEqual(set(f["window"]), {"from", "to"})

    def test_other_keys_are_kept_exactly(self):
        self.run_read()
        p = loop.path_for(self.work, "invoice-chasing")
        r = json.loads(p.read_text(encoding="utf-8"))
        r["spec"] = {"verdict": "ready", "note": "kept as is"}
        r["portfolio"] = {"rank": 2}
        r["future_key"] = [1, 2, 3]
        p.write_text(json.dumps(r), encoding="utf-8")
        self.run_read()
        after = self.record("invoice-chasing")
        for key in ("spec", "portfolio", "future_key", "brief", "schema", "bet"):
            self.assertEqual(after[key], r[key])
        self.assertEqual(after["landed"]["status"], "watch")

    def test_evals_and_cost_are_context_and_cost_over_budget_is_flagged(self):
        self.run_read()
        p = loop.path_for(self.work, "quote-drafting-assistant")
        r = json.loads(p.read_text(encoding="utf-8"))
        src = "Illustrative eval-kit run"
        r["evals"] = {"pass_rate": loop.figure(0.91, "share", src, "2026-11-01", "2026-11-20", "2026-11-20")}
        fig = loop.figure(12000, "tokens per task", "Illustrative usage export", "2026-11-01", "2026-11-20", "2026-11-20")
        budget = loop.figure(9000, "tokens per task", "landing brief", "2026-11-01", "2026-11-20", "2026-11-20")
        share = loop.figure(0.3333, "share over budget", "cost-budget-check", "2026-11-01", "2026-11-20", "2026-11-20")
        line = {"actual": fig, "budget": budget, "against_budget": share, "budget_status": "over budget"}
        r["cost"] = {"tool": "cost-budget-check 0.3.1", "budget_status": "over budget", "lines": {"tokens_per_task": line}}
        p.write_text(json.dumps(r), encoding="utf-8")
        b = next(b for b in self.run_read()["bets"] if b["id"] == "B1")
        self.assertEqual(b["status"], "landed")  # context never changes the call
        self.assertEqual(b["context"]["evals"][0]["value"], 0.91)
        self.assertNotIn("cost", b["context"])  # cited whole by the cost check, never re-listed
        self.assertIn("over-cost-budget", {f["code"] for f in b["flags"]})
        self.assertEqual(b["cost"]["budget_status"], "over budget")
        self.assertIn("given cost is over budget", b["next_step"])
        md = did_it_land.to_markdown(did_it_land.read(self.bundle, self.work))
        self.assertIn("From the project file, evals", md)
        self.assertIn("Cost: over budget, from the cost check.", md)
        self.assertIn("the cost word is cited from `cost-budget-check 0.3.1`", md.split("## For your engineers", 1)[1])
        self.assertIn("AI usage per task 12,000 against 9,000, 33% over", md)

    def test_the_cost_word_is_cited_never_recomputed(self):
        # The record says within budget although the actual is above the budget: the read prints the record's word.
        self.run_read()
        p = loop.path_for(self.work, "quote-drafting-assistant")
        r = json.loads(p.read_text(encoding="utf-8"))
        fig = loop.figure(12000, "tokens per task", "Illustrative usage export", "2026-11-01", "2026-11-20", "2026-11-20")
        r["cost"] = {
            "tool": "cost-budget-check 0.3.1",
            "budget_status": "within budget",
            "lines": {"tokens_per_task": {"actual": fig, "budget": fig, "budget_status": "within budget"}},
        }
        p.write_text(json.dumps(r), encoding="utf-8")
        b = next(b for b in self.run_read()["bets"] if b["id"] == "B1")
        self.assertEqual(b["cost"]["budget_status"], "within budget")
        self.assertNotIn("over-cost-budget", {f["code"] for f in b["flags"]})
        self.assertTrue(b["next_step"].endswith("given cost is within budget."))

    def test_a_cost_key_without_a_budget_word_reads_not_checked(self):
        self.run_read()
        p = loop.path_for(self.work, "quote-drafting-assistant")
        r = json.loads(p.read_text(encoding="utf-8"))
        r["cost"] = {"tokens_per_task": loop.figure(12000, "tokens per task", "Illustrative usage export", "2026-11-01", "2026-11-20", "2026-11-20")}
        p.write_text(json.dumps(r), encoding="utf-8")
        b = next(b for b in self.run_read()["bets"] if b["id"] == "B1")
        self.assertEqual(b["cost"]["text"], "cost not checked: run cost-budget-check")
        self.assertTrue(b["next_step"].endswith("decide whether to scale the bet."))

    def test_a_brief_edited_after_the_record_opened_holds_landed(self):
        self.run_read()
        brief = self.d / "acme" / "briefs" / "quote-drafting.md"
        brief.write_text(brief.read_text(encoding="utf-8").replace("**Bar:** 40%", "**Bar:** 35%"), encoding="utf-8")
        b = next(b for b in did_it_land.read(self.bundle, self.work)["bets"] if b["id"] == "B1")
        self.assertEqual(b["status"], "watch")
        self.assertIn("brief-changed", {f["code"] for f in b["flags"]})

    def test_a_foreign_record_is_refused_and_left_alone(self):
        p = loop.path_for(self.work, "payment-links")
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"schema": "something-else/9"}), encoding="utf-8")
        with self.assertRaises(did_it_land.BundleError):
            did_it_land.read(self.bundle, self.work)
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"schema": "something-else/9"})

    def test_cli_writes_records_and_pages(self):
        out = self.d / "out"
        subprocess.run([sys.executable, str(SCRIPTS / "did_it_land.py"), "read", str(self.bundle), "--loop", str(self.work), "--out", str(out)], check=True, capture_output=True)
        self.assertTrue((out / "read.html").exists() and (out / "read.md").exists() and (out / "read.json").exists())
        self.assertTrue(loop.path_for(self.work, "mobile-job-scheduler").exists())


class LiveData(unittest.TestCase):
    def test_period_labels(self):
        self.assertEqual(str(from_run.period_end("2026-11-16")), "2026-11-16")
        self.assertEqual(str(from_run.period_end("2026-02")), "2026-02-28")
        self.assertEqual(str(from_run.period_end("2026-W47")), "2026-11-22")
        self.assertEqual(str(from_run.period_end("2026-Q3")), "2026-09-30")
        with self.assertRaises(from_run.RunError):
            from_run.period_end("last week")

    def test_amplitude_through_the_vendored_collector(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "run"
            periods = ["--period", "2026-11-16=2026-11-10..2026-11-16", "--period", "2026-11-23=2026-11-17..2026-11-23"]
            cmd = [sys.executable, str(SCRIPTS / "vendor" / "from_amplitude.py"), "--chart", str(LIVE / "amplitude-seg.json"), "--metric", "Quote draft acceptance rate"]
            cmd += periods + ["--aggregate", "mean", "--project", "Acme web", "--retrieved-at", "2026-11-24", "--run", str(run)]
            subprocess.run(cmd, check=True, capture_output=True)
            rows = from_run.rows_from_run(run)
            out = Path(d) / "metrics.csv"
            from_run.append_csv(rows, out)
            text = out.read_text(encoding="utf-8")
        self.assertEqual([(r["date"], r["value"]) for r in rows], [("2026-11-16", 41.2857), ("2026-11-23", 43.2857)])
        self.assertIn("Amplitude (Acme web)", rows[0]["source"])
        self.assertTrue(text.startswith("metric,date,value,source,last_synced"))

    def test_billing_becomes_arr(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "run" / "data"
            data.mkdir(parents=True)
            rows = [{"account": "a", "month": "2026-10", "arr": 100.0}, {"account": "b", "month": "2026-10", "arr": 50.0}, {"account": "a", "month": "2026-11", "arr": 120.0}]
            billing = {"source": "billing", "system": "Stripe", "query_or_url": "invoices", "retrieved_at": "2026-11-25", "origin": "inv.json", "rows": rows}
            (data / "billing.json").write_text(json.dumps(billing), encoding="utf-8")
            got = from_run.rows_from_run(Path(d) / "run")
        self.assertEqual([(r["metric"], r["date"], r["value"]) for r in got], [("ARR", "2026-10-31", 150.0), ("ARR", "2026-11-30", 120.0)])

    def test_no_collected_data(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(from_run.RunError):
            from_run.rows_from_run(Path(d))


class Html(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = did_it_land.read(FIXTURE)
        cls.page = render_html.page(cls.result)

    def test_self_contained(self):
        self.assertIsNone(re.search(r'(src|href)="https?:', self.page))
        self.assertNotIn("@import", self.page)
        self.assertEqual(self.page.count("@font-face"), 3)

    def test_every_status_word_prints(self):
        for b in self.result["bets"]:
            word = b["status"] or "not read"
            self.assertIn(f">{word}</span>", self.page)

    def test_illustrative_and_not_proof(self):
        self.assertIn('<span class="sk-ill">Illustrative</span>', self.page)
        self.assertIn(":root{--ill:#74A5DA}", self.page, "the Illustrative tag is blue")
        self.assertIn("is not proof", self.page)

    def test_the_visuals_draw_only_figures_the_page_prints(self):
        self.assertEqual(len(svgkit.svgs_in(self.page.split('<div class="sc scg"', 1)[1].split('<div class="next">', 1)[0])), 7, "one range line per project read")
        self.assertEqual(svgkit.unprinted(self.page), [])
        text = svgkit.page_text(self.page)
        for b in self.result["bets"]:
            for r in b["figures"].get("series", []):
                self.assertIn(r["shown"].upper(), text, f"{b['name']}: a reading the line draws is not printed")

    def test_green_and_red_only_beside_their_words(self):
        body = self.page.split("</style>", 1)[1]
        self.assertNotIn("var(--landed)", body)
        self.assertNotIn("var(--stalled)", body)
        # The status colour is a class: the word's mark, and the dot in the same row.
        for row in re.findall(r'<div class="sc-r">.*?</div>', body):
            for word in ("landed", "stalled", "watch"):
                if f'class="ac {word}"' in row:
                    self.assertIn(f'<span class="st {word}">{word}</span>', row)
        css = self.page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertNotIn('class="ok"', body, "the template's green healthy-side band")
        self.assertNotIn("rgba(92,211,140", body)
        self.assertIn(".sc-rl .ac.landed{fill:var(--landed)}", css)

    def test_the_scorecard_states_its_answer(self):
        labels = re.findall(r'role="img" aria-label="([^"]+)"', self.page)
        self.assertEqual(labels, [render_html.verdict(self.result)])

    def test_public_copy_uses_plain_words(self):
        public = svgkit.page_text(self.page.split("For your engineers", 1)[0]).lower()
        for word in (" bet ", " bets ", " bar ", "within-noise", "source-stale", "verified_jumps", ".json"):
            self.assertNotIn(word, public)
        self.assertIn("landing brief</b>, a one-page plan", self.page)
        twin = did_it_land.to_markdown(self.result).split("## For your engineers", 1)[0].lower()
        for name, text in {"page": public, "twin": twin}.items():
            for word in (r"\brecords?\b", r"\bbets?\b", r"\bbar\b", r"\bprds?\b", r"\barr\b", r"\btokens?\b", r"within-noise", r"verified_jumps", r"\.json"):
                self.assertIsNone(re.search(word, text), f"{name}: {word}")

    def test_no_text_is_smaller_than_12px(self):
        css = " ".join(re.findall(r"<style>(.*?)</style>", self.page, re.DOTALL)) + " " + " ".join(re.findall(r'style="([^"]*)"', self.page))
        sizes = re.findall(r"font-size\s*:\s*([\d.]+)px", css) + re.findall(r"font\s*:[^;{}]*?(?<![\w.-])([\d.]+)px", css)
        sizes += re.findall(r'font-size="([\d.]+)"', self.page)
        self.assertTrue(sizes)
        self.assertEqual([s for s in sizes if float(s) < 12], [])
        self.assertNotRegex(css, r"font-size\s*:\s*[\d.]+r?em")
        before, after = ".a{font:400 10px/16px var(--mono)}.b{font-size:10.5px}.c{font-size:13px}", ".a{font:400 12px/16px var(--mono)}.b{font-size:12px}.c{font-size:13px}"
        self.assertEqual(render_html.floor_fonts(before), after)

    def test_the_scorecard_is_rows_with_no_text_inside_a_picture(self):
        frames = svgkit.frames_in(self.page)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].count('<div class="sc-r">'), len(self.result["bets"]))
        self.assertEqual(svgkit.svgs_with_text(self.page), [], "text inside an SVG")
        self.assertEqual(svgkit.scaled_svgs_in(self.page), [], "a picture with a viewBox would scale")
        for b in [b for b in self.result["bets"] if b["status"] and "move" in b["figures"]]:
            f = b["figures"]
            tail = " · LOWER IS BETTER" if f["bar"]["better"] == "lower" else ""
            why = render_html.past_target(b).upper()
            why = f'<span class="sc-why">{why}</span>' if why else ""
            line = f'<span class="sc-l">{render_html.prior_shown(f)} <i>→</i> <b>{f["current"]["shown"]}</b> · TARGET {f["bar"]["shown"]}{tail}{why}</span>'
            self.assertIn(line, frames[0], b["name"])

    def test_the_prior_prints_to_the_actuals_decimals(self):
        def fig(mean, base, now):
            return {"move": {"baseline_mean": mean, "baseline_shown": base}, "current": {"shown": now}}

        self.assertEqual(render_html.prior_shown(fig(21.6667, "21.67%", "43%")), "22%")
        self.assertEqual(render_html.prior_shown(fig(16.9167, "16.92%", "18.1%")), "16.9%")
        self.assertEqual(render_html.prior_shown(fig(2060, "2,060", "2,100")), "2,060")
        self.assertEqual(render_html.prior_shown(fig(0.3, "$0.3", "$0.25")), "$0.30")
        self.assertIsNone(render_html.prior_shown({"current": {"shown": "43%"}}))
        frame = svgkit.frames_in(self.page)[0]
        for prior, now in re.findall(r'<span class="sc-l">([^ <]+) <i>→</i> <b>([^<]+)</b>', frame):
            self.assertEqual(render_html.decimals(prior), render_html.decimals(now), (prior, now))

    def test_a_watch_row_past_its_target_says_why_under_its_figure(self):
        lines, whys, words = {}, {}, {}
        for row in re.findall(r'<div class="sc-r">(.*?)</div>', svgkit.frames_in(self.page)[0]):
            name = re.search(r'<span class="sc-n">([^<]+)</span>', row).group(1)
            fig = re.search(r'<span class="sc-l">(.*?)</span>(?=<span class="sc-s">)', row).group(1)
            why = re.search(r'<span class="sc-why">([^<]+)</span>', fig)
            whys[name] = why.group(1) if why else ""
            lines[name] = re.sub(r"<[^>]+>", "", re.sub(r'<span class="sc-why">[^<]*</span>', "", fig))
            words[name] = re.findall(r'<span class="sc-w">([^<]+)</span>', row)
        self.assertEqual(lines["Payment links"], "16.9% → 18.1% · TARGET 18%")
        self.assertEqual(whys["Payment links"], "PAST TARGET · INSIDE NORMAL UPS AND DOWNS")
        self.assertEqual(whys["Automatic reminders"], "PAST TARGET · OUTCOME FELL")
        self.assertEqual(whys["SMS reminders"], "PAST TARGET · DATA OUT OF DATE")
        self.assertEqual(whys["Invoice auto-match"], "PAST TARGET · DATA JUMPED")
        self.assertEqual(whys["Invoice chasing"], "", "a watch row short of its target needs no reason")
        self.assertIn(".sc-why{display:block}", self.page, "the reason is its own line under the figure")
        # The status cell keeps only the status word and the cost word: no reason under it.
        for name, ws in words.items():
            self.assertTrue(all(w.startswith("cost ") or w == "not read" for w in ws), (name, ws))
        for b in self.result["bets"]:
            held = b["status"] == "watch" and "the call is held" in b["reason"]
            self.assertEqual(bool(render_html.past_target(b)), held, b["name"])
            for fl in b["flags"]:
                if held and fl["code"] in render_html.HELD:
                    self.assertIn(fl["code"], render_html.PAST, "every held code has its plain words")

    def test_a_lower_is_better_figure_says_so(self):
        frame = svgkit.frames_in(self.page)[0]
        self.assertIn("<b>35</b> · TARGET 30 · LOWER IS BETTER</span>", frame)
        self.assertEqual(frame.count("LOWER IS BETTER"), sum(1 for b in self.result["bets"] if b["status"] and b["figures"]["bar"]["better"] == "lower"))

    def test_the_figure_column_is_numerals_and_uppercase_words(self):
        for f in re.findall(r'<span class="sc-l">(.*?)</span>', svgkit.frames_in(self.page)[0]):
            text = re.sub(r"<[^>]+>", "", f)
            self.assertEqual(text, text.upper(), f)

    def test_labels_render_12px_and_names_14px(self):
        css = self.page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertEqual(set(svgkit.font_sizes(css)), {"var(--sc-m)", "var(--sc-n)"})
        self.assertIn("--sc-m:calc(12px / var(--sc-z))", css)
        self.assertIn("--sc-n:calc(14px / var(--sc-z))", css)
        self.assertIn(".scg{--sc-z:1;", css, "a sample page has no zoom")

    def test_no_box_inside_the_scorecard_and_no_overlap(self):
        css = self.page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertEqual(svgkit.boxes_in_frames(self.page, css), [])
        self.assertNotIn("position:absolute", svgkit.SCORECARD_CSS)
        self.assertNotIn('class="chip"', self.page.split("For your engineers", 1)[0])

    def test_no_legacy_svgkit_primitive_draws_on_the_page(self):
        import warnings

        self.assertEqual(svgkit.legacy_in(self.page), [])
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            render_html.page(self.result)

    def test_one_scale_for_the_frame_so_every_target_tick_lines_up(self):
        frame = svgkit.frames_in(self.page)[0]
        ticks = set(re.findall(r'class="tg" x="([^"]+)"', frame))
        self.assertEqual(len(ticks), 1, ticks)

    def test_only_the_focus_project_is_open(self):
        opened = re.findall(r'<details class="proj" open><summary><h2 id="([^"]+)"', self.page)
        self.assertEqual(opened, [self.result["bets"][0]["slug"]])
        rows = re.findall(r'<details class="proj row" id="([^"]+)"><summary><span class="pn">', self.page)
        self.assertEqual(rows, [b["slug"] for b in self.result["bets"][1:]], "every other project folds as one hairline row")
        self.assertEqual(self.page.count("<h2"), 1, "no large heading per folded project")
        self.assertNotRegex(self.page, r"Project \d\d", "no PROJECT 0X chip")

    def test_the_page_reads_in_under_1000_words_unfolded(self):
        from html.parser import HTMLParser

        class Visible(HTMLParser):
            """Text a reader sees as the page opens: a closed fold shows only its summary line."""

            def __init__(self) -> None:
                super().__init__()
                self.stack: list[list[bool]] = []  # per open <details>: [is open, inside its summary]
                self.skip = 0
                self.words = 0

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.stack.append(["open" in dict(attrs), False])
                elif tag == "summary" and self.stack:
                    self.stack[-1][1] = True
                elif tag in ("style", "title"):
                    self.skip += 1

            def handle_endtag(self, tag):
                if tag == "details" and self.stack:
                    self.stack.pop()
                elif tag == "summary" and self.stack:
                    self.stack[-1][1] = False
                elif tag in ("style", "title"):
                    self.skip -= 1

            def handle_data(self, data):
                if not self.skip and all(is_open or in_summary for is_open, in_summary in self.stack):
                    self.words += len(data.split())

        v = Visible()
        v.feed(self.page)
        self.assertLess(v.words, 1000, v.words)

    def test_dates_never_break(self):
        self.assertIn(".nd{white-space:nowrap}", self.page)
        body = re.sub(r'<span class="nd">\d{4}-\d{2}-\d{2}</span>', "", self.page.split("<body>", 1)[1])
        self.assertEqual(re.findall(r"\d{4}-\d{2}-\d{2}", re.sub(r"<[^>]*>", " ", body)), [])
        self.assertEqual(
            render_html.nowrap_dates('<p title="2026-01-02">by 2026-01-02</p><code>2026-01-02</code>'),
            '<p title="2026-01-02">by <span class="nd">2026-01-02</span></p><code>2026-01-02</code>',
        )

    def test_the_header_prints_the_plain_name_and_the_code_name_is_for_engineers(self):
        self.assertEqual(re.search(r'<span class="sk-meta"><span>(.*?)</span>', self.page).group(1), "Did it land?")
        public, fold = self.page.split("For your engineers", 1)
        self.assertNotIn("did-it-land", svgkit.page_text(public).lower())
        self.assertIn(f"Built by {self.result['computed_by']}.", fold)
        self.assertIn(f"Built by {self.result['computed_by']}.", did_it_land.to_markdown(self.result).split("## For your engineers", 1)[1])

    def test_source_text_is_escaped(self):
        result = json.loads(json.dumps(self.result))
        result["bets"][0]["name"] = '<script>alert("x")</script>'
        page = render_html.page(result)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_no_em_dashes(self):
        self.assertNotIn(chr(0x2014), self.page)


class Sample(unittest.TestCase):
    ROOT = SKILL.parent.parent
    EX = ROOT / "examples" / "acme"

    def command(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Sample", 1)[1].split("```bash", 1)[1].split("```", 1)[0].strip()
        self.assertEqual(len(section.splitlines()), 1, "the sample command must be one line")
        return section.split()

    def test_the_readme_command_reproduces_the_sample_byte_for_byte(self):
        cmd = self.command()
        self.assertEqual(cmd[0], "python3")
        with tempfile.TemporaryDirectory() as d:
            work = Path(d) / "repo"
            shutil.copytree(self.ROOT / "skills", work / "skills")
            shutil.copytree(self.EX, work / "examples" / "acme")
            committed_record = (self.EX / "landing" / "quote-drafting.json").read_bytes()
            shutil.rmtree(work / "examples" / "acme" / "landing")
            (work / "examples" / "acme" / "did-it-land.html").unlink()
            (work / "examples" / "acme" / "did-it-land.md").unlink()
            subprocess.run([sys.executable, *cmd[1:]], cwd=work, check=True, capture_output=True)
            self.assertEqual((work / "examples/acme/did-it-land.html").read_bytes(), (self.EX / "did-it-land.html").read_bytes())
            self.assertEqual((work / "examples/acme/did-it-land.md").read_bytes(), (self.EX / "did-it-land.md").read_bytes())
            self.assertEqual((work / "examples/acme/landing/quote-drafting.json").read_bytes(), committed_record)

    def test_the_markdown_twin_is_the_read(self):
        result = did_it_land.read(self.EX / "bundle.json", self.EX)
        self.assertEqual((self.EX / "did-it-land.md").read_text(encoding="utf-8"), did_it_land.to_markdown(result))

    def test_sample_reads_seven_bets_with_all_three_words(self):
        result = did_it_land.read(self.EX / "bundle.json")
        self.assertEqual(len(result["bets"]), 7)
        self.assertIn("quote-drafting", [b["slug"] for b in result["bets"]])
        self.assertEqual({b["status"] for b in result["bets"]}, {"landed", "watch", "stalled"})

    def test_briefs_are_the_canonical_ones(self):
        canon = json.loads((self.EX / "bundle.json").read_text(encoding="utf-8"))
        for b in canon["bets"]:
            self.assertEqual(Path(b["brief"]).stem, b["slug"])

    def test_record_adds_only_the_landed_key_to_upstream(self):
        record = json.loads((self.EX / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))
        upstream = json.loads((self.EX / "upstream" / "quote-drafting.json").read_text(encoding="utf-8"))
        self.assertEqual(set(record), set(upstream) | {"landed"})
        for key in upstream:
            self.assertEqual(record[key], upstream[key])  # read, cited, never rewritten
        self.assertEqual(record["brief"]["path"], "briefs/quote-drafting.md")
        self.assertEqual(record["landed"]["status"], "landed")

    def test_landed_prints_the_cited_cost_check_beside_the_call(self):
        record = json.loads((self.EX / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))
        landed = record["landed"]
        self.assertEqual(landed["cost_check"], {"budget_status": record["cost"]["budget_status"], "cited_from": record["cost"]["tool"]})
        self.assertEqual(landed["cost_check"]["budget_status"], "over budget")
        self.assertIn("given cost is over budget", landed["next_step"])
        md = (self.EX / "did-it-land.md").read_text(encoding="utf-8")
        cited = record["cost"]["tool"]  # the version comes from the upstream record, not this test
        self.assertIn("- **landed**. Past the target of 40% by 2026-11-15. Cost: over budget, from the cost check.", md)
        self.assertIn(f"the cost word is cited from `{cited}`", md.split("## For your engineers", 1)[1])
        self.assertIn("cost per task $0.0338 against $0.027, 25% over", md)
        self.assertIn('<span class="st landed">landed</span><span class="sc-w">cost over budget</span>', (self.EX / "did-it-land.html").read_text(encoding="utf-8"))

    def test_next_steps_are_due_on_or_after_the_read(self):
        result = did_it_land.read(self.EX / "bundle.json", self.EX)
        for b in result["bets"]:
            if b["status"]:
                self.assertGreaterEqual(b["due"], result["as_of"][:10], b["name"])
        record = json.loads((self.EX / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(record["landed"]["next_step_due"], record["landed"]["as_of"][:10])

    def test_the_quote_drafting_move_is_a_realistic_multiple_of_the_spread(self):
        record = json.loads((self.EX / "landing" / "quote-drafting.json").read_text(encoding="utf-8"))
        f = record["landed"]["figures"]
        self.assertTrue(3 <= f["move_z"]["value"] <= 6, f["move_z"]["value"])
        self.assertEqual((f["current"]["value"], f["at_date"]["value"], f["bar"]["value"]), (43.0, 41.0, 40.0))

    def test_selection_and_focus_print_in_ink(self):
        page = (self.EX / "did-it-land.html").read_text(encoding="utf-8")
        css = page.split("<style>", 1)[1].split("</style>", 1)[0]
        # The vendored stylesheet paints them green; this page's own rules come after it and win.
        self.assertGreater(css.rindex("::selection{background:var(--t1)"), css.rindex("::selection{background:var(--landed)"))
        self.assertGreater(css.rindex(":focus-visible{outline-color:var(--t1)}"), css.rindex(":focus-visible{outline:2px solid var(--landed)"))

    def test_the_page_follows_the_sample_anatomy(self):
        page = (self.EX / "did-it-land.html").read_text(encoding="utf-8")
        body = page.split('<main class="solo">', 1)[1]
        order = ['class="sk-hdr"', "<h1>", 'class="sc scg"', "What to do next", '<details class="proj" open>', "For your engineers"]
        at = [body.index(x) for x in order]
        self.assertEqual(at, sorted(at))
        self.assertIn("<h1>Quote drafting landed. Job scheduler stalled. Five more are on watch.</h1>", body)
        self.assertEqual(body.count('<div class="next">'), 1, "one next step leads the page")
        self.assertIn('<span class="o">Head of Product, Field squad</span><span class="d"><span class="nd">2026-12-10</span></span>', body)
        self.assertIn("<details><summary>For your engineers</summary>", body)


class FullColumn(unittest.TestCase):
    """Text runs the full content column, as wide as the scorecard frame (2026-11-27): no max-width on h1, .lede or p."""

    def test_page_css_sets_no_max_width_on_text(self) -> None:
        css = render_html.PAGE_CSS
        for selector, body in re.findall(r"([^{}]+)\{([^}]*max-width:[^}]*)\}", css):
            if re.search(r"(^|[\s,])(h1|\.lede|p|li|\.next|\.note|\.figs|\.checks)([\s,:.]|$)", selector):
                self.assertIn("max-width:none", body, selector)
        self.assertIn(".solo h1,.solo .lede,.solo .next,.solo .slide p,.solo .slide li,.solo .sc-c,.sk figcaption{max-width:none}", css)
        self.assertIn("text-wrap:balance", css)
        self.assertIn(".solo .slide p,.solo .slide li,.solo .sc-c{text-wrap:pretty}", css)

    def test_the_override_comes_after_the_template_cap(self) -> None:
        page = (Path(__file__).resolve().parents[1] / "examples/acme/did-it-land.html").read_text(encoding="utf-8")
        css = page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertGreater(css.rindex("{max-width:none}"), css.index("max-width:62ch"))


if __name__ == "__main__":
    unittest.main()
