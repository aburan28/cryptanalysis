#!/usr/bin/env python3
"""Version the corrected N41 geometry-row input builder without changing frozen v1."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "query_protocol_v2.json"
    if output.exists():
        raise FileExistsError("preserve first version-two query protocol")
    previous = json.loads((HERE / "query_protocol.json").read_text())
    failure = json.loads((HERE / "input_failure_v1.json").read_text())
    if failure["status"] != "FROZEN_INPUT_BUILDER_FAILURE":
        raise ValueError("version-one failure receipt changed")
    if failure["query_protocol_sha256"] != sha(HERE / "query_protocol.json"):
        raise ValueError("version-one protocol changed")
    previous["input_version"] = 2
    previous["supersedes_protocol_sha256"] = sha(HERE / "query_protocol.json")
    previous["version_one_failure_sha256"] = sha(HERE / "input_failure_v1.json")
    previous["source_sha256"].pop("make_input.py")
    previous["source_sha256"]["make_input_v2.py"] = sha(HERE / "make_input_v2.py")
    previous["source_sha256"]["run_query_v2.py"] = sha(HERE / "run_query_v2.py")
    previous["source_sha256"]["freeze_query_v2.py"] = sha(Path(__file__))
    previous["input_correction"] = "Read the first four fields of each six-field frozen geometry row; retain the full source geometry digest."
    output.write_text(json.dumps(previous, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
