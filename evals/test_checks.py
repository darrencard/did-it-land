"""The ported checks agree with the Throughline tests they came from."""

import unittest

import _path  # noqa: F401
import checks


class MetricMatch(unittest.TestCase):
    def test_same_metric_ignores_case_and_whitespace(self):
        self.assertTrue(checks.same_metric(" Agent-led deploys", "agent-led deploys "))
        self.assertFalse(checks.same_metric("activation", "activation rate"))

    def test_exact_match_wins(self):
        self.assertEqual(checks.match_metric("v0 arr", ["v0 ARR", "Activation rate"]), ("v0 ARR", "exact"))

    def test_token_subset_matches(self):
        self.assertEqual(checks.match_metric("activation", ["v0 ARR", "Activation rate"]), ("Activation rate", "tokens"))

    def test_no_match_and_empty(self):
        self.assertEqual(checks.match_metric("logo retention", ["Activation rate"]), (None, "none"))
        self.assertEqual(checks.match_metric("", ["Activation rate"]), (None, "none"))


class Significance(unittest.TestCase):
    def test_too_few_points(self):
        self.assertIsNone(checks.assess_significance([47, 47]))
        self.assertIsNone(checks.assess_significance(None))

    def test_flat_is_within_noise(self):
        s = checks.assess_significance([47, 47, 47, 47, 47])
        self.assertTrue(s.within_noise)
        self.assertTrue(s.needs_experiment)
        self.assertEqual(s.direction, "flat")

    def test_small_wobble_is_within_noise(self):
        self.assertTrue(checks.assess_significance([44, 46, 45, 47, 47]).within_noise)

    def test_clear_break_is_significant(self):
        s = checks.assess_significance([10, 11, 10, 11, 40])
        self.assertFalse(s.within_noise)
        self.assertEqual(s.direction, "up")

    def test_single_prior_move_uses_its_size(self):
        s = checks.assess_significance([10, 12, 13])
        self.assertEqual(s.sigma, 1.41)  # sqrt(|2|), as significance.ts does


class Sensor(unittest.TestCase):
    def test_stale(self):
        self.assertEqual(checks.assess_sensor(50, [10, 11, 10, 11]).state, "stale")

    def test_jump(self):
        self.assertEqual(checks.assess_sensor(2, [10, 11, 10, 11, 60]).state, "jumpy")

    def test_fresh_in_range(self):
        self.assertEqual(checks.assess_sensor(2, [10, 11, 10, 11, 12]).state, "healthy")

    def test_flat_and_fresh_is_not_flagged(self):
        self.assertEqual(checks.assess_sensor(1, [99.98, 99.98, 99.98, 99.98]).state, "healthy")

    def test_own_stale_limit(self):
        self.assertEqual(checks.assess_sensor(50, [1, 2, 3], stale_after_hours=200).state, "healthy")


class Coupling(unittest.TestCase):
    def test_outcome_improves_with_metric(self):
        self.assertEqual(checks.classify_coupling([1, 2, 3], [10, 8, 6], "lower").verdict, "coupled")

    def test_metric_up_outcome_worse(self):
        self.assertEqual(checks.classify_coupling([1, 2, 3], [10, 12, 14], "lower").verdict, "decoupled")

    def test_metric_up_outcome_flat(self):
        self.assertEqual(checks.classify_coupling([1, 2, 3], [100, 101, 100], "higher").verdict, "flat")

    def test_thin_history(self):
        self.assertEqual(checks.classify_coupling([1, 2], [10, 8], "lower").verdict, "thin")

    def test_metric_not_climbing(self):
        self.assertEqual(checks.classify_coupling([3, 2, 1], [10, 10, 11], "higher").verdict, "coupled")
        self.assertEqual(checks.classify_coupling([3, 2, 1], [10, 9, 8], "higher").verdict, "flat")


class Integrity(unittest.TestCase):
    def test_green_over_red(self):
        self.assertEqual(checks.classify_integrity("green", ["red"]), ("green over red", "red"))

    def test_one_step(self):
        self.assertEqual(checks.classify_integrity("green", ["amber"])[0], "one step rosier")
        self.assertEqual(checks.classify_integrity("amber", ["red"])[0], "one step rosier")

    def test_aligned_or_gloomier(self):
        self.assertEqual(checks.classify_integrity("amber", ["amber"])[0], "aligned")
        self.assertEqual(checks.classify_integrity("red", ["green"])[0], "aligned")

    def test_worst_anchor_wins(self):
        self.assertEqual(checks.classify_integrity("green", ["green", "red"]), ("green over red", "red"))


if __name__ == "__main__":
    unittest.main()
