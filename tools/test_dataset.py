"""Tests of what ./dataset reads from the runs it leaves.

  python3 -m unittest discover -s tools
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

DATASET = Path(__file__).resolve().parent.parent / "dataset"


class Summary(unittest.TestCase):

    def test_a_report_holding_a_number_too_long_for_python_is_summed_up_all_the_same(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "long" / "run-1" / "report.json"
            report.parent.mkdir(parents=True)
            report.write_text('{"tool": {"version": "2.4.0"}, "totals": {"requests": 12, "operations": 3}, '
                              '"findings": [{"body": {"value": {"n": %s}}}]}' % ("1" * 10000), encoding="utf-8")

            # 4300 is Python's own limit from 3.11 on; earlier versions ignore the variable.
            done = subprocess.run([str(DATASET), "summary", temp], capture_output=True, text=True,
                                  env=dict(os.environ, PYTHONINTMAXSTRDIGITS="4300"))

            self.assertEqual(0, done.returncode, done.stderr)
            self.assertRegex(done.stdout, r"long\s+run-1\s+12\s+3")


class Licences(unittest.TestCase):

    def test_every_api_has_its_row_in_licences_md(self):
        root = DATASET.parent
        rows = set(re.findall(r"^\| \[`([^`]+)`\]\(apis/", (root / "LICENCES.md").read_text(encoding="utf-8"),
                              re.MULTILINE))
        apis = {p.parent.name for p in (root / "apis").glob("*/compose.yaml")}

        self.assertEqual(set(), apis - rows, "APIs with no row in LICENCES.md")
        self.assertEqual(set(), rows - apis, "rows in LICENCES.md for no API")


if __name__ == "__main__":
    unittest.main()
