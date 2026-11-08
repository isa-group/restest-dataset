#!/usr/bin/env python3
"""What a showcase campaign leaves behind: one entry per API, then the release's manifest.

  tools/showcase.py entry <run-dir> --api ID --version X.Y.Z --started TIME --runner LABEL
                          [--restest CMD] --into DIR
  tools/showcase.py manifest <artifacts-dir> --apis FILE --version X.Y.Z --archive-sha256 HEX
                          --budget 15m --seed N --started TIME --repository OWNER/NAME --commit SHA
                          --workflow-run URL --out DIR --notes FILE

.github/workflows/showcase.yml runs `entry` at the end of each API's job, whatever happened in it,
and `manifest` once every job is over. The README's "The showcase" says what the manifest holds.
Needs Python 3.9 or later; nothing else.
"""

import argparse
import collections
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FORMAT = 1
API_LOG_LINES = 2000  # the end of the API's own log is kept, where a failure to start shows


def fail(message):
    print(f"showcase: {message}", file=sys.stderr)
    sys.exit(1)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_line(path):
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return lines[0].strip() if lines else None


def last_line(path):
    if not path.is_file():
        return None
    lines = [line for line in tail(path, 20) if line.strip()]
    return lines[-1].strip() if lines else None


def tail(path, count):
    with open(path, "rb") as f:
        return [line.decode("utf-8", errors="replace").rstrip("\n")
                for line in collections.deque(f, maxlen=count)]


# -------------------------------------------------------------------------------------------- entry

def outcome_of(run_dir, version):
    """What became of the API's run: its outcome, the reason when there is no report, and RESTest's
    exit code when it ended."""
    code = first_line(run_dir / "exit-code")
    exit_code = int(code) if code and code.lstrip("-").isdigit() else None
    if (run_dir / "pull-failed.txt").is_file():
        return "imagesNotPulled", first_line(run_dir / "pull-failed.txt"), None
    report = run_dir / "report.json"
    if report.is_file():
        written_by = (json.loads(report.read_text(encoding="utf-8")).get("tool") or {}).get("version")
        if written_by != version:
            fail(f"{report} was written by RESTest {written_by}, and the campaign is of {version}")
        return "ran", None, exit_code
    if (run_dir / "start-failed.txt").is_file():
        return "apiDidNotStart", first_line(run_dir / "start-failed.txt"), None
    last = last_line(run_dir / "restest.log") or last_line(run_dir.parent.parent / "dataset.log")
    if exit_code is not None:
        reason = f"RESTest ended with {exit_code} and left no report"
    else:
        reason = "RESTest did not finish: it ran out of time, or the run stopped before it ended"
    return "noReport", f"{reason}: {last}" if last else reason, exit_code


def machine(runner, restest, where):
    """The machine the API was tested on, as far as the job can tell."""
    memory = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        match = re.search(r"^MemTotal:\s+(\d+) kB", meminfo.read_text(), re.MULTILINE)
        memory = round(int(match.group(1)) / 2 ** 20) if match else None
    java = None
    if restest:
        try:
            out = subprocess.run([*restest, "version"], capture_output=True, text=True, timeout=60).stdout
            java = next((line[len("Java "):].strip() for line in out.splitlines() if line.startswith("Java ")),
                        None)
        except (OSError, subprocess.SubprocessError):
            java = None
    image = " ".join(v for v in (os.environ.get("ImageOS"), os.environ.get("ImageVersion")) if v) or None
    return {"label": runner, "image": image, "cpus": os.cpu_count(), "memoryGiB": memory,
            "freeDiskGiB": round(shutil.disk_usage(where).free / 2 ** 30), "java": java}


def entry(run_dir, api, version, started, runner, restest, into):
    """Writes into `into` the API's entry.json and the files the campaign keeps of its run."""
    run_dir, into = Path(run_dir), Path(into)
    into.mkdir(parents=True, exist_ok=True)
    outcome, reason, exit_code = outcome_of(run_dir, version)
    for name in ("report.json", "report.html", "restest.log"):
        if (run_dir / name).is_file():
            shutil.copyfile(run_dir / name, into / name)
    if (run_dir / "api.log").is_file():
        (into / "api.log").write_text("\n".join(tail(run_dir / "api.log", API_LOG_LINES)) + "\n",
                                      encoding="utf-8")
    record = {
        "id": api,
        "outcome": outcome,
        "reason": reason,
        "exitCode": exit_code,
        "credentials": first_line(run_dir / "credentials.txt"),
        "leftAlone": first_line(run_dir / "left-alone.txt"),
        "startedAt": started,
        "finishedAt": now(),
        "runner": machine(runner, restest, run_dir if run_dir.exists() else into),
    }
    (into / "entry.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


# ----------------------------------------------------------------------------------------- manifest

def iso_duration(budget):
    """15m -> PT15M, as report.json writes lengths of time."""
    match = re.fullmatch(r"([1-9][0-9]*)([smh])", budget)
    if not match:
        fail(f"{budget!r} is not a budget such as 90s, 15m or 1h")
    return f"PT{match.group(1)}{match.group(2).upper()}"


def manifest(artifacts, apis, version, archive_sha256, budget, seed, started, repository, commit,
             workflow_run, out, notes):
    """Writes into `out` the release's manifest.json and each API's two reports, and the release's
    notes into `notes`. Fails when an API of the campaign left no entry."""
    artifacts, out = Path(artifacts), Path(out)
    described = json.loads(Path(apis).read_text(encoding="utf-8"))
    missing = [a["id"] for a in described if not (artifacts / f"run-{a['id']}" / "entry.json").is_file()]
    if missing:
        fail(f"no entry for {', '.join(missing)}: their jobs left nothing behind; run them again")
    out.mkdir(parents=True, exist_ok=True)
    rows, runner = [], None
    for api in described:
        folder = artifacts / f"run-{api['id']}"
        record = json.loads((folder / "entry.json").read_text(encoding="utf-8"))
        runner = runner or record["runner"]
        assets = {}
        for name, key in (("report.json", "report"), ("report.html", "page")):
            assets[key] = None
            if (folder / name).is_file():
                assets[key] = f"{api['id']}.{name}"
                shutil.copyfile(folder / name, out / assets[key])
        rows.append({
            "id": api["id"],
            "title": api["title"],
            "license": (api.get("upstream") or {}).get("license"),
            "upstream": (api.get("upstream") or {}).get("repository"),
            "outcome": record["outcome"],
            "reason": record["reason"],
            "exitCode": record["exitCode"],
            "credentials": record["credentials"],
            "leftAlone": record["leftAlone"],
            "startedAt": record["startedAt"],
            "finishedAt": record["finishedAt"],
            **assets,
        })
    document = {
        "format": FORMAT,
        "restest": {"version": version, "archive": f"restest-{version}.tgz", "sha256": archive_sha256},
        "budget": iso_duration(budget),
        "seed": str(seed),
        "runner": runner,
        "startedAt": started,
        "finishedAt": now(),
        "dataset": {"repository": repository, "commit": commit},
        "workflowRun": workflow_run,
        "apis": rows,
    }
    (out / "manifest.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    Path(notes).write_text(release_notes(document), encoding="utf-8")
    return document


def release_notes(document):
    counts = collections.Counter(row["outcome"] for row in document["apis"])
    said = {"ran": "tested", "apiDidNotStart": "did not start", "imagesNotPulled": "could not be pulled",
            "noReport": "left no report"}
    outcomes = ", ".join(f"{counts[k]} {v}" for k, v in said.items() if counts[k])
    runner = document["runner"] or {}
    return (f"RESTest {document['restest']['version']} on the {len(document['apis'])} APIs of this dataset "
            f"({outcomes}), {document['budget'][2:].lower()} each with seed {document['seed']}, on GitHub's "
            f"{runner.get('label')} runners ({runner.get('cpus')} CPUs, {runner.get('memoryGiB')} GiB), "
            f"started {document['startedAt']}.\n\n"
            "`manifest.json` says how each API went; `<api>.report.html` is RESTest's report of that API, "
            "and `<api>.report.json` the same as data.\n")


# ---------------------------------------------------------------------------------------- commands

def main(argv=None):
    parser = argparse.ArgumentParser(prog="showcase", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("entry", help="what became of one API's run")
    p.add_argument("run_dir")
    for option in ("--api", "--version", "--started", "--runner", "--into"):
        p.add_argument(option, required=True)
    p.add_argument("--restest", help="the command that runs RESTest, to ask it which Java it runs on")

    p = commands.add_parser("manifest", help="the release's manifest, from every API's entry")
    p.add_argument("artifacts")
    for option in ("--apis", "--version", "--archive-sha256", "--budget", "--seed", "--started",
                   "--repository", "--commit", "--workflow-run", "--out", "--notes"):
        p.add_argument(option, required=True)

    args = parser.parse_args(argv)
    if args.command == "entry":
        record = entry(args.run_dir, args.api, args.version, args.started, args.runner,
                       shlex.split(args.restest) if args.restest else None, args.into)
        print(f"{args.api}: {record['outcome']}" + (f" ({record['reason']})" if record["reason"] else ""))
    else:
        document = manifest(args.artifacts, args.apis, args.version, args.archive_sha256, args.budget,
                            args.seed, args.started, args.repository, args.commit, args.workflow_run,
                            args.out, args.notes)
        print(f"{len(document['apis'])} APIs in {Path(args.out) / 'manifest.json'}")


if __name__ == "__main__":
    main()
