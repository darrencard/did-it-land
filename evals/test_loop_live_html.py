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
        self.assertIn("Context from the loop record, evals", md)
        self.assertIn("Cost: over budget, cited from cost-budget-check 0.3.1.", md)
        self.assertIn("tokens per task 12,000 against 9,000, 33% over", md)

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
        self.assertGreater(len(svgkit.svgs_in(self.page)), 7)
        self.assertEqual(svgkit.unprinted(self.page), [])
        text = svgkit.page_text(self.page)
        for b in self.result["bets"]:
            for r in b["figures"].get("series", []):
                self.assertIn(r["shown"].upper(), text, f"{b['name']}: a reading the line draws is not printed")

    def test_green_and_red_only_beside_their_words(self):
        body = self.page.split("</style>", 1)[1]
        # Take out every mark that prints its own word: the template's status mark, and svgkit's status_word.
        rest = re.sub(r'<span class="st (landed|stalled)">\1</span>', "", body)
        rest = re.sub(r'<g class="sk-st">(?:(?!</g>).)*?var\(--(landed|stalled)\)(?:(?!</g>).)*?>\1</text></g>', "", rest, flags=re.I)
        for word in ("landed", "stalled"):
            self.assertNotIn(f"var(--{word})", rest)
            self.assertNotIn(f"st {word}", rest)
        self.assertGreater(body.count("var(--landed)"), 0)
        self.assertNotIn('class="ok"', body, "the template's green healthy-side band")
        self.assertNotIn("rgba(92,211,140", body)

    def test_each_visual_states_its_answer(self):
        for b in self.result["bets"]:
            if not b["status"]:
                continue
            f = b["figures"]
            labels = re.findall(rf'aria-label="({re.escape(b["name"])}: [^"]+)"', self.page)
            self.assertEqual(len(labels), 3, b["name"])  # the small multiple, the wide chart and the tall one
            for label in labels:
                self.assertIn(f"target of {f['bar']['shown']}", label)
                self.assertTrue(label.endswith(f"{b['status'].capitalize()}."), label)

    def test_public_copy_uses_plain_words(self):
        public = svgkit.page_text(self.page.split("For your engineers", 1)[0]).lower()
        for word in (" bet ", " bets ", " bar ", "within-noise", "source-stale", "verified_jumps", ".json"):
            self.assertNotIn(word, public)
        self.assertIn("landing brief</b>, a one-page plan", self.page)

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
        self.assertIn("- **landed**. Past the bar of 40% by 2026-11-15. Cost: over budget, cited from cost-budget-check 0.3.1.", md)
        self.assertIn("cost per task $0.0338 against $0.027, 25% over", md)
        self.assertIn('<span class="chip" title="cited from cost-budget-check 0.3.1">cost over budget</span>', (self.EX / "did-it-land.html").read_text(encoding="utf-8"))

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
        order = ['class="sk-hdr"', "<h1>", 'class="minis"', "What to do next", 'class="cols"', "For your engineers"]
        at = [body.index(x) for x in order]
        self.assertEqual(at, sorted(at))
        self.assertIn("<h1>Quote drafting landed. Job scheduler stalled. Five more are on watch.</h1>", body)
        self.assertEqual(body.count('<div class="next">'), 1, "one next step leads the page")
        self.assertIn('<span class="o">Head of Product, Field squad</span><span class="d">2026-12-10</span>', body)
        self.assertIn("<details><summary>For your engineers</summary>", body)


if __name__ == "__main__":
    unittest.main()
