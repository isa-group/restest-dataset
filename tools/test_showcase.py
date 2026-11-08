"""Tests of tools/showcase.py, on run folders made up as ./dataset run leaves them.

  python3 -m unittest discover -s tools
"""

import json
import tempfile
import unittest
from pathlib import Path

import showcase

VERSION = "2.4.0"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def report(version=VERSION):
    return json.dumps({"tool": {"version": version}})


class Campaign(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_dir(self, api, files=None):
        folder = self.root / "out" / api / "run-1"
        folder.mkdir(parents=True)
        for name, text in (files or {}).items():
            write(folder / name, text)
        return folder

    def entry(self, api, folder):
        return showcase.entry(run_dir=folder, api=api, version=VERSION, started="2026-11-08T10:00:00Z",
                              runner="ubuntu-24.04", restest=None, into=self.root / "artifacts" / f"run-{api}")


class Entry(Campaign):

    def test_a_run_with_a_report_keeps_both_reports_its_lines_and_the_end_of_the_api_log(self):
        api_log = "".join(f"line {n}\n" for n in range(1, 3001))
        folder = self.run_dir("petstore", {
            "report.json": report(), "report.html": "<html></html>", "exit-code": "1\n",
            "credentials.txt": "fixed, user u: header:Authorization\n", "left-alone.txt": "none\n",
            "restest.log": "started\nfinished\n", "api.log": api_log})

        record = self.entry("petstore", folder)

        self.assertEqual("ran", record["outcome"])
        self.assertIsNone(record["reason"])
        self.assertEqual(1, record["exitCode"])
        self.assertEqual("fixed, user u: header:Authorization", record["credentials"])
        self.assertEqual("none", record["leftAlone"])
        self.assertEqual("2026-11-08T10:00:00Z", record["startedAt"])
        self.assertEqual("ubuntu-24.04", record["runner"]["label"])
        kept = self.root / "artifacts" / "run-petstore"
        self.assertEqual(sorted(["entry.json", "report.json", "report.html", "restest.log", "api.log"]),
                         sorted(p.name for p in kept.iterdir()))
        lines = (kept / "api.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(showcase.API_LOG_LINES, len(lines))
        self.assertEqual("line 3000", lines[-1])
        self.assertEqual(record, json.loads((kept / "entry.json").read_text(encoding="utf-8")))

    def test_an_api_that_did_not_start_says_why_in_one_line(self):
        folder = self.run_dir("slow", {"start-failed.txt": "slow did not answer /ready within 600s (last: None)\n"
                                                       "some log line\n"})

        record = self.entry("slow", folder)

        self.assertEqual("apiDidNotStart", record["outcome"])
        self.assertEqual("slow did not answer /ready within 600s (last: None)", record["reason"])
        self.assertIsNone(record["exitCode"])

    def test_images_that_could_not_be_pulled_are_not_blamed_on_the_api(self):
        folder = self.run_dir("pulled", {
            "pull-failed.txt": "toomanyrequests: You have reached your pull rate limit\n"})

        record = self.entry("pulled", folder)

        self.assertEqual("imagesNotPulled", record["outcome"])
        self.assertEqual("toomanyrequests: You have reached your pull rate limit", record["reason"])

    def test_restest_ending_without_a_report_gives_its_exit_code_and_its_last_line(self):
        folder = self.run_dir("broken", {
            "exit-code": "4\n", "restest.log": "sending\nRESTest went wrong: boom\n\n"})

        record = self.entry("broken", folder)

        self.assertEqual("noReport", record["outcome"])
        self.assertEqual(4, record["exitCode"])
        self.assertEqual("RESTest ended with 4 and left no report: RESTest went wrong: boom", record["reason"])

    def test_restest_killed_before_it_ended_has_no_exit_code(self):
        folder = self.run_dir("killed", {"restest.log": "sending\n"})

        record = self.entry("killed", folder)

        self.assertEqual("noReport", record["outcome"])
        self.assertIsNone(record["exitCode"])
        self.assertTrue(record["reason"].startswith("RESTest did not finish"), record["reason"])
        self.assertTrue(record["reason"].endswith(": sending"), record["reason"])

    def test_a_job_that_stopped_before_restest_started_takes_the_last_line_the_dataset_printed(self):
        write(self.root / "out" / "dataset.log", "== early run 1/1\nTraceback ...\nKeyError: 'paths'\n")
        folder = self.run_dir("early")

        record = self.entry("early", folder)

        self.assertEqual("noReport", record["outcome"])
        self.assertTrue(record["reason"].endswith(": KeyError: 'paths'"), record["reason"])

    def test_a_report_by_another_version_than_the_campaigns_stops_the_job(self):
        folder = self.run_dir("other", {"report.json": report("2.3.0"), "exit-code": "0\n"})

        with self.assertRaises(SystemExit):
            self.entry("other", folder)


class Manifest(Campaign):

    def manifest(self, apis):
        apis_file = self.root / "apis.json"
        write(apis_file, json.dumps(apis))
        return showcase.manifest(
            artifacts=self.root / "artifacts", apis=apis_file, version=VERSION, archive_sha256="abc123",
            budget="15m", seed="42", started="2026-11-08T10:00:00Z", repository="isa-group/restest-dataset",
            commit="deadbeef", workflow_run="https://github.com/isa-group/restest-dataset/actions/runs/1",
            out=self.root / "release", notes=self.root / "notes.md")

    def test_the_manifest_says_how_the_campaign_was_made_and_how_each_api_went(self):
        self.entry("petstore", self.run_dir("petstore", {
            "report.json": report(), "report.html": "<html></html>", "exit-code": "0\n",
            "credentials.txt": "none\n", "left-alone.txt": "none\n"}))
        self.entry("slow", self.run_dir("slow", {"start-failed.txt": "slow did not start\n"}))

        document = self.manifest([
            {"id": "petstore", "title": "Swagger Petstore",
             "upstream": {"license": "Apache", "repository": "https://github.com/swagger-api/swagger-petstore"}},
            {"id": "slow", "title": "Slow", "upstream": {"license": "MIT", "repository": None}},
        ])

        self.assertEqual(1, document["format"])
        self.assertEqual({"version": VERSION, "archive": "restest-2.4.0.tgz", "sha256": "abc123"},
                         document["restest"])
        self.assertEqual("PT15M", document["budget"])
        self.assertEqual("42", document["seed"])
        self.assertEqual("ubuntu-24.04", document["runner"]["label"])
        self.assertEqual({"repository": "isa-group/restest-dataset", "commit": "deadbeef"}, document["dataset"])
        petstore, slow = document["apis"]
        self.assertEqual(("petstore", "Swagger Petstore", "Apache", "ran", 0),
                         (petstore["id"], petstore["title"], petstore["license"], petstore["outcome"],
                          petstore["exitCode"]))
        self.assertEqual(("petstore.report.json", "petstore.report.html"), (petstore["report"], petstore["page"]))
        self.assertEqual(("apiDidNotStart", "slow did not start", None, None, None),
                         (slow["outcome"], slow["reason"], slow["upstream"], slow["report"], slow["page"]))
        release = self.root / "release"
        self.assertEqual(["manifest.json", "petstore.report.html", "petstore.report.json"],
                         sorted(p.name for p in release.iterdir()))
        self.assertEqual(document, json.loads((release / "manifest.json").read_text(encoding="utf-8")))
        notes = (self.root / "notes.md").read_text(encoding="utf-8")
        self.assertIn("RESTest 2.4.0 on the 2 APIs of this dataset (1 tested, 1 did not start), 15m each "
                      "with seed 42", notes)

    def test_an_api_whose_job_left_nothing_stops_the_manifest_and_is_named(self):
        self.entry("petstore", self.run_dir("petstore", {"report.json": report(), "exit-code": "0\n"}))

        with self.assertRaises(SystemExit):
            self.manifest([{"id": "petstore", "title": "P", "upstream": {"license": None, "repository": None}},
                           {"id": "lost", "title": "L", "upstream": {"license": None, "repository": None}}])
        self.assertFalse((self.root / "release" / "manifest.json").exists())

    def test_budgets_are_written_as_report_json_writes_lengths_of_time(self):
        self.assertEqual(["PT20S", "PT1M", "PT1M30S", "PT15M", "PT1H30M", "PT1H", "PT5H"],
                         [showcase.iso_duration(b) for b in ("20s", "60s", "90s", "15m", "90m", "1h", "5h")])


if __name__ == "__main__":
    unittest.main()
