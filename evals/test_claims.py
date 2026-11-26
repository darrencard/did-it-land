"""The overclaim check blocks prose that says more than the read shows."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import FIXTURE, SCRIPTS

# isort: split
import did_it_land

RESULT = did_it_land.read(FIXTURE)


def rules(prose: str) -> set:
    return {f["rule"] for f in did_it_land.check_prose(RESULT, prose)}


class Overclaims(unittest.TestCase):
    def test_a_faithful_summary_passes(self):
        prose = (
            "Quote drafting assistant landed: acceptance reached 41% by the date and is 43% now. "
            "Payment links is watch: 18.1% is past the 18% bar, but the move is within noise, so we will run an experiment. "
            "Mobile job scheduler stalled at 2,100 against a bar of 3,000."
        )
        self.assertEqual(did_it_land.check_prose(RESULT, prose), [])

    def test_causal_claim(self):
        self.assertIn("causal-claim", rules("Quote drafting assistant landed, and it drove the rise in win rate."))
        self.assertIn("causal-claim", rules("The rise is thanks to the new assistant."))

    def test_figure_not_computed(self):
        self.assertIn("figure-not-computed", rules("Invoice chasing is watch, with DSO down 12 days."))

    def test_status_mismatch(self):
        self.assertIn("status-mismatch", rules("Payment links landed this month."))

    def test_success_claim_for_a_bet_not_landed(self):
        self.assertIn("success-claim", rules("Automatic reminders is watch, but it worked."))

    def test_status_word_missing(self):
        self.assertIn("status-missing", rules("Mobile job scheduler is behind."))

    def test_banned_words(self):
        self.assertIn("banned-word", rules("These bets unlock a seamless experience."))

    def test_dates_are_not_figures(self):
        self.assertEqual(rules("Invoice chasing is watch until 2026-12-31."), set())

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.md"
            good.write_text("Invoice auto-match is watch: the source jumped to 95%.", encoding="utf-8")
            bad = Path(d) / "bad.md"
            bad.write_text("Invoice auto-match landed and caused a 77% saving.", encoding="utf-8")
            cmd = [sys.executable, str(SCRIPTS / "did_it_land.py"), "check", str(FIXTURE)]
            self.assertEqual(subprocess.run(cmd + [str(good)], capture_output=True).returncode, 0)
            out = subprocess.run(cmd + [str(bad)], capture_output=True, text=True)
            self.assertEqual(out.returncode, 1)
            for rule in ("causal-claim", "figure-not-computed", "status-mismatch"):
                self.assertIn(rule, out.stdout)


if __name__ == "__main__":
    unittest.main()
