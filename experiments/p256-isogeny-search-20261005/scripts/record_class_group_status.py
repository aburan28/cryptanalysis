#!/usr/bin/env python3
"""Freeze a read-only status snapshot of the long PARI class-group attempt."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="p256-classgroup-default")
    parser.add_argument("--attempt-id", default="pari-quadclassunit-default")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    state: dict[str, Any] = json.loads(
        command("docker", "inspect", args.container, "--format", "{{json .State}}")
    )
    stats: dict[str, str] = json.loads(
        command("docker", "stats", args.container, "--no-stream", "--format", "{{json .}}")
    )
    affinity_text = command("docker", "exec", args.container, "taskset", "-pc", "1")
    affinity = affinity_text.rsplit(":", 1)[-1].strip()
    log_lines = command("docker", "logs", "--tail", "1", args.container).splitlines()
    last_log = json.loads(log_lines[-1]) if log_lines else {}

    observed = datetime.now(timezone.utc)
    started = parse_time(state["StartedAt"])
    result_path = args.result if args.result.is_absolute() else ROOT / args.result
    result_present = result_path.is_file()
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_present else None
    payload = {
        "schema_version": 1,
        "attempt_id": args.attempt_id,
        "observed_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "started_at": state["StartedAt"],
        "elapsed_lower_bound_seconds": (observed - started).total_seconds(),
        "status": state["Status"],
        "container": args.container,
        "cpu_affinity": f"CPU {affinity}",
        "cpu_percent_observed": float(stats["CPUPerc"].rstrip("%")),
        "memory_observed": stats["MemUsage"].split(" / ", 1)[0],
        "method": "PARI quadclassunit (Buchmann-McCurley)",
        "correctness_basis_if_completed": "conditional on GRH using PARI's factor-base bound",
        "last_log_event": last_log.get("event"),
        "output_path": str(result_path.relative_to(ROOT)),
        "output_present": result_present,
        "result": result,
        "mathematical_evidence": result_present and state["Status"] == "exited" and state["ExitCode"] == 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": payload["status"],
        "elapsed_lower_bound_seconds": payload["elapsed_lower_bound_seconds"],
        "output_present": result_present,
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
