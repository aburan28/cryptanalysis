#!/usr/bin/env python3
"""Freeze the corrected geometry builder and manifest-key lookup."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "query_protocol_v3.json"
    if output.exists():
        raise FileExistsError("preserve first version-three query protocol")
    previous = json.loads((HERE / "query_protocol_v2.json").read_text())
    failure = json.loads((HERE / "input_failure_v2.json").read_text())
    if (failure["status"] != "FROZEN_INPUT_BUILDER_FAILURE" or
            failure["query_protocol_sha256"] != sha(HERE / "query_protocol_v2.json") or
            failure["public_input_created"]):
        raise ValueError("version-two failure receipt changed")
    previous["input_version"] = 3
    previous["supersedes_protocol_sha256"] = sha(HERE / "query_protocol_v2.json")
    previous["version_two_failure_sha256"] = sha(HERE / "input_failure_v2.json")
    previous["source_sha256"].pop("make_input_v2.py")
    previous["source_sha256"].pop("run_query_v2.py")
    previous["source_sha256"].pop("freeze_query_v2.py")
    previous["source_sha256"]["make_input_v3.py"] = sha(HERE / "make_input_v3.py")
    previous["source_sha256"]["run_query_v3.py"] = sha(HERE / "run_query_v3.py")
    previous["source_sha256"]["freeze_query_v3.py"] = sha(Path(__file__))
    previous["input_correction"] = "Use first four of six geometry fields and resolve the frozen builder hash by its own filename."
    output.write_text(json.dumps(previous, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
