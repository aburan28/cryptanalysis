#!/usr/bin/env python3
"""Select CI jobs from a complete local Git diff, without API path limits."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
INFRA = ("scripts/ci_scope.py", ".github/ci/", ".github/actions/ci-scope/")


def matches(path, pattern):
    """Match repository globs: * stays within a directory; ** crosses it."""
    expression = ""
    i = 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            expression += "(?:.*/)?"
            i += 3
        elif pattern[i:i + 2] == "**":
            expression += ".*"
            i += 2
        elif pattern[i] == "*":
            expression += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            expression += "[^/]"
            i += 1
        else:
            expression += re.escape(pattern[i])
            i += 1
    return re.fullmatch(expression, path) is not None


def select(jobs, paths, workflow):
    if paths is None or any(
        path == ".github/workflows/" + workflow
        or any(path == prefix or path.startswith(prefix) for prefix in INFRA)
        for path in paths
    ):
        return dict.fromkeys(jobs, True)
    return {
        job: any(matches(path, pattern) for path in paths for pattern in patterns)
        for job, patterns in jobs.items()
    }


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def changed_paths(event_name, event):
    if event_name in ("schedule", "workflow_dispatch"):
        return None
    if event_name == "pull_request":
        # checkout's merge commit fixes the base used to test this PR. An
        # updated base branch cannot change the comparison while we wait.
        try:
            base = git("rev-parse", "HEAD^1").decode().strip()
        except subprocess.CalledProcessError:
            base = event["pull_request"]["base"]["sha"]
    elif event_name == "merge_group":
        base = event["merge_group"]["base_sha"]
    elif event_name == "push":
        base = event["before"]
    else:
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{40}", base) or base == "0" * 40:
        return None
    try:
        git("cat-file", "-e", base + "^{commit}")
    except subprocess.CalledProcessError:
        # Pushes can contain many commits or be force pushes. Fetch that
        # exact prior commit, never a moving branch tip; no file blobs needed.
        git("fetch", "--no-tags", "--filter=blob:none", "--depth=1", "origin", base)
    raw = git("diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--")
    # --no-renames includes both names of moves, including deleted paths.
    return raw.decode("utf-8", "surrogateescape").rstrip("\0").split("\0") if raw else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--event-file", default=os.environ.get("GITHUB_EVENT_PATH"))
    args = parser.parse_args()
    jobs = json.loads((ROOT / ".github/ci/scopes.json").read_text())[args.workflow]
    try:
        event = json.loads(Path(args.event_file).read_text()) if args.event_file else {}
        paths = changed_paths(args.event_name, event)
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        # A missing base, fetch failure or malformed event must run the tests.
        print(f"::warning::Cannot determine changed paths ({type(error).__name__}); running all jobs.")
        paths = None
    chosen = select(jobs, paths, args.workflow)
    encoded = json.dumps(chosen, separators=(",", ":"))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("selected=" + encoded + "\n")
    print(encoded)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("### CI scope\n\n")
            stream.write("Full validation (manual/scheduled run or unavailable diff).\n" if paths is None
                         else f"Compared all {len(paths)} changed paths (including removals).\n")
            for job, run in chosen.items():
                stream.write(f"- `{job}`: {'run' if run else 'skip (unrelated paths)'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
