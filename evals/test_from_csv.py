"""from_csv.py builds the same bundle a person would write by hand."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import FIXTURE, SCRIPTS

# isort: split
import did_it_land
import from_csv

CSV = FIXTURE.parent.parent / "acme-csv"


class FromCsv(unittest.TestCase):
    def test_csv_read_matches_the_json_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(FIXTURE.parent / "briefs", Path(d) / "briefs")
            out = Path(d) / "bundle.json"
            bundle = from_csv.build(CSV / "metrics.csv", CSV / "bets.csv", "2026-11-26T09:00:00Z", "Acme", True)
            out.write_text(json.dumps(bundle), encoding="utf-8")
            via_csv = did_it_land.read(out)
        direct = did_it_land.read(FIXTURE)
        self.assertEqual([(b["id"], b["status"]) for b in via_csv["bets"]], [(b["id"], b["status"]) for b in direct["bets"]])
        self.assertEqual(via_csv["counts"], direct["counts"])

    def test_every_problem_is_listed(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "m.csv"
            m.write_text("metric,date,value,source\nA,2026-01-05,10,x\nA,2026-01-12,ten,x\nA,2026-01-19,11,y\n", encoding="utf-8")
            b = Path(d) / "b.csv"
            b.write_text("id,name,shipped\n1,X,2026-01-01\n", encoding="utf-8")
            with self.assertRaises(did_it_land.BundleError) as e:
                from_csv.build(m, b, "2026-02-01")
        msg = str(e.exception)
        self.assertIn("not a number", msg)
        self.assertIn("two sources", msg)
        self.assertIn("missing column(s): brief", msg)


class Init(unittest.TestCase):
    def test_init_then_from_csv_then_read(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "read"
            run = [sys.executable, str(SCRIPTS / "did_it_land.py")]
            out = subprocess.run(run + ["init", str(folder)], capture_output=True, text=True, check=True)
            self.assertIn("from_csv.py", out.stdout)
            # Fill the scaffold with one bet, using the template brief as written.
            (folder / "briefs" / "example-brief.md").rename(folder / "briefs" / "quote.md")
            weeks = ["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-14", "2026-09-28", "2026-10-12", "2026-11-09"]
            values = [22, 23, 21, 22, 23, 27, 31, 35, 41]
            with (folder / "metrics.csv").open("a", encoding="utf-8") as f:
                for w, v in zip(weeks, values, strict=True):
                    f.write(f"Quote draft acceptance rate,{w},{v},test export,2026-11-12T00:00:00Z\n")
            with (folder / "bets.csv").open("a", encoding="utf-8") as f:
                f.write("B1,Quote drafting,2026-09-07,briefs/quote.md,2026-08-01,green,,\n")
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "from_csv.py"),
                    str(folder / "metrics.csv"),
                    str(folder / "bets.csv"),
                    "--as-of",
                    "2026-11-12T09:00:00Z",
                    "-o",
                    str(folder / "bundle.json"),
                ],
                check=True,
                capture_output=True,
            )
            md = subprocess.run(run + ["read", str(folder / "bundle.json")], capture_output=True, text=True, check=True).stdout
        self.assertIn("## Quote drafting: landed", md)

    def test_init_refuses_a_folder_with_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "keep.txt").write_text("x", encoding="utf-8")
            out = subprocess.run([sys.executable, str(SCRIPTS / "did_it_land.py"), "init", d], capture_output=True, text=True)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("not empty", out.stderr)


if __name__ == "__main__":
    unittest.main()
