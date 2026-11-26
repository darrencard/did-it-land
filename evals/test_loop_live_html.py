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
        r["cost"] = {"tokens_per_task": loop.figure(12000, "tokens", "Illustrative usage export", "2026-11-01", "2026-11-20", "2026-11-20")}
        p.write_text(json.dumps(r), encoding="utf-8")
        b = next(b for b in self.run_read()["bets"] if b["id"] == "B1")
        self.assertEqual(b["status"], "landed")  # context never changes the call
        self.assertEqual(b["context"]["evals"][0]["value"], 0.91)
        self.assertIn("over-cost-budget", {f["code"] for f in b["flags"]})
        self.assertIn("Context from the loop record, evals", did_it_land.to_markdown(did_it_land.read(self.bundle, self.work)))

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
            self.assertIn(f'<span class="st {b["status"] or "none"}">{b["status"] or "not read"}</span>', self.page)

    def test_illustrative_and_not_proof(self):
        self.assertIn("Illustrative: sample data", self.page)
        self.assertIn("is not proof", self.page)

    def test_source_text_is_escaped(self):
        result = json.loads(json.dumps(self.result))
        result["bets"][0]["name"] = '<script>alert("x")</script>'
        page = render_html.page(result)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_no_em_dashes(self):
        self.assertNotIn(chr(0x2014), self.page)


if __name__ == "__main__":
    unittest.main()
