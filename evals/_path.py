"""Puts the skill's scripts on the import path for the tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "did-it-land" / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "acme" / "bundle.json"
sys.path.insert(0, str(SCRIPTS))
