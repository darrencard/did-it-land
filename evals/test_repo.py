"""House rules for every file in the repository: wording, versions and the vendored brief parser."""

import json
import re
import tomllib
import unittest

from _path import ROOT, SCRIPTS

# isort: split
import did_it_land
import landing_brief

TEXT = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json", ".toml", ".yml", ".txt"} and not {".git", ".ruff_cache", "runs", "vendor"} & set(p.parts)]
BANNED = re.compile(r"\b(AI-powered|unlock|supercharge|seamless|robust|get started)\b", re.I)
# The rule names in the overclaim check and the tests that exercise it may name the banned words.
ALLOWED_BANNED = {"did_it_land.py", "test_repo.py", "test_claims.py"}


class Wording(unittest.TestCase):
    def test_no_em_or_en_dashes(self):
        for p in TEXT:
            text = p.read_text(encoding="utf-8")
            self.assertNotIn(chr(0x2014), text, p)
            self.assertNotIn(chr(0x2013), text, p)

    def test_no_banned_words(self):
        for p in TEXT:
            if p.name in ALLOWED_BANNED:
                continue
            m = BANNED.search(p.read_text(encoding="utf-8"))
            self.assertIsNone(m, f"{p}: {m and m.group(0)}")

    def test_fixture_is_marked_illustrative(self):
        bundle = json.loads((ROOT / "evals/fixtures/acme/bundle.json").read_text(encoding="utf-8"))
        self.assertTrue(bundle["illustrative"])
        for m in bundle["metrics"].values():
            self.assertTrue(m["source"].startswith("Illustrative"))
        for p in (ROOT / "evals/fixtures/acme/briefs").glob("*.md"):
            self.assertIn("Illustrative", p.read_text(encoding="utf-8"))


class ReadmeSample(unittest.TestCase):
    def test_the_readme_sample_is_real_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        block = readme.split("## What you get", 1)[1].split("```text", 1)[1].split("```", 1)[0]
        output = " ".join(did_it_land.to_markdown(did_it_land.read(ROOT / "evals/fixtures/acme/bundle.json")).replace("**", "").split())
        for item in block.split("\n- ")[1:]:
            self.assertIn(" ".join(item.split()), output)


class PythonFloor(unittest.TestCase):
    def test_every_entry_script_checks_the_version_before_anything_else(self):
        for p in [SCRIPTS / "did_it_land.py", SCRIPTS / "from_csv.py", SCRIPTS / "from_run.py", ROOT / "examples/acme/sample.py"]:
            text = p.read_text(encoding="utf-8")
            guard = text.index("if sys.version_info < (3, 11)")
            self.assertIn("needs Python 3.11 or later; try python3.12", text, p)
            for later in ("sys.path.insert", "open(", "read_text(", "write_text(", "shutil."):
                if later in text:
                    self.assertLess(guard, text.index(later), f"{p}: {later} before the version check")


class Versions(unittest.TestCase):
    def test_versions_agree(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        skill = re.search(r'version: "([^"]+)"', (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")).group(1)
        self.assertEqual({plugin, project, skill}, {"0.3.2"})


class BriefSchema(unittest.TestCase):
    def test_the_template_parses(self):
        brief = landing_brief.parse((SCRIPTS.parent / "assets/landing-brief-template.md").read_text(encoding="utf-8"))
        self.assertEqual(brief.line, "model call")

    def test_a_broken_brief_lists_every_problem(self):
        with self.assertRaises(landing_brief.BriefError) as e:
            landing_brief.parse("## Landing brief\n\n- **Metric:** Activation\n- **Bar:** soon\n")
        self.assertIn("problem is missing", str(e.exception))
        self.assertIn("by is missing", str(e.exception))


if __name__ == "__main__":
    unittest.main()
