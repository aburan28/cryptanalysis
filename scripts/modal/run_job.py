"""Sandbox entrypoint: clone an immutable revision and run one checked Sage job."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


REPO = Path("/workspace/cryptanalysis")
RESULTS = Path("/results")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def tool_versions() -> dict[str, object]:
    versions = {}
    for name, command in {
        "rustc": ["rustc", "--version"],
        "cargo": ["cargo", "--version"],
        "cxx": ["g++", "--version"],
        "cryptominisat": ["cryptominisat5", "--version"],
        "zstd": ["zstd", "--version"],
    }.items():
        executable = shutil.which(command[0])
        if executable is None:
            versions[name] = {"status": "missing"}
            continue
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=15)
            versions[name] = {"path": executable, "returncode": result.returncode,
                              "first_line": (result.stdout or result.stderr).splitlines()[:1]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            versions[name] = {"path": executable, "error": f"{type(exc).__name__}: {exc}"}
    return versions


def run(args: argparse.Namespace) -> int:
    result_dir = RESULTS / args.job_id
    result_dir.mkdir(parents=True, exist_ok=False)
    arguments = json.loads(args.args_json)
    if not isinstance(arguments, list) or not all(isinstance(x, str) for x in arguments):
        raise ValueError("--args-json must be a list of strings")
    record = {"job_id": args.job_id, "revision_requested": args.revision,
              "script": args.script, "arguments": arguments,
              "started_utc": stamp(), "status": "setup", "platform": platform.platform(),
              "requested_resources": {"cpu": os.environ.get("MODAL_REQUESTED_CPU"),
                                      "memory_mb": os.environ.get("MODAL_REQUESTED_MEMORY_MB"),
                                      "timeout_s": os.environ.get("MODAL_REQUESTED_TIMEOUT_S")}}
    write_json(result_dir / "status.json", record)
    write_json(result_dir / "tool-versions.json", tool_versions())
    try:
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout",
                        "https://github.com/aburan28/cryptanalysis.git", str(REPO)], check=True)
        subprocess.run(["git", "-C", str(REPO), "checkout", "--detach", args.revision], check=True)
        revision = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
        if revision != args.revision:
            raise RuntimeError(f"checkout mismatch: {revision}")
        record["revision"] = revision
        source = REPO / "third_party/sage-binary"
        source.parent.mkdir(parents=True, exist_ok=True)
        if source.exists() or source.is_symlink():
            raise RuntimeError("repository unexpectedly contains a Sage build")
        source.symlink_to("/opt/sage-binary", target_is_directory=True)
        checker = REPO / "experiments/sage-binary-arithmetic/runtime_check.py"
        checker.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2("/opt/modal/runtime_check.py", checker)
        hardware = REPO / "experiments/sage-binary-hardware"
        hardware.mkdir(parents=True, exist_ok=True)
        for name in ("validate_compatibility.py", "test_portability.py", "test_hardware.py", "load_hardware.py"):
            shutil.copy2(Path("/opt/modal") / name, hardware / name)
        shutil.copy2("/opt/modal/remote_sage.sh", REPO / "sage")
        (REPO / "sage").chmod(0o755)
        script = (REPO / args.script).resolve()
        if not script.is_relative_to(REPO) or not script.is_file():
            raise ValueError("script must be a file inside the checked-out repository")
        if script.suffix not in (".py", ".sage"):
            raise ValueError("script must end in .py or .sage")
        record["script_sha256"] = hashlib.sha256(script.read_bytes()).hexdigest()
        record["sage_source_sha256"] = hashlib.sha256(Path("/opt/modal/sage-source.tar.gz").read_bytes()).hexdigest()
        env = os.environ.copy()
        env["SAGE_SOURCE_SHA256"] = record["sage_source_sha256"]
        subprocess.run(["/opt/sage-binary/sage", "-python", "/opt/modal/accept_linux_runtime.py", str(REPO)],
                       check=True, env=env)
        with (result_dir / "sage-runtime-info.json").open("w") as output:
            subprocess.run([str(REPO / "sage"), "--runtime-info"], check=True, stdout=output, cwd=REPO)
        subprocess.run([str(REPO / "sage"), "-python", str(hardware / "validate_compatibility.py"),
                        "--backends", "cpu", "--out", str(result_dir / "compatibility")],
                       check=True, cwd=REPO)
        record["status"] = "running"
        record["online_timing_note"] = "Job wall time includes remote startup; workload must record its own online interval."
        write_json(result_dir / "status.json", record)
        command = [str(REPO / "sage")]
        if script.suffix == ".py":
            command.append("-python")
        command.extend([str(script), *arguments])
        with (result_dir / "job.log").open("w", buffering=1) as log:
            process = subprocess.Popen(command, cwd=REPO, env={**env, "MODAL_JOB_OUTPUT": str(result_dir)},
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            code = process.wait()
        record["exit_code"] = code
        record["status"] = "completed" if code == 0 else "failed"
        return code
    except BaseException as exc:
        record["status"] = "setup_failed" if record["status"] == "setup" else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["finished_utc"] = stamp()
        write_json(result_dir / "status.json", record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--args-json", default="[]")
    args = parser.parse_args()
    if len(args.revision) != 40 or any(ch not in "0123456789abcdef" for ch in args.revision):
        parser.error("--revision must be a full lowercase commit SHA")
    if not args.job_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in args.job_id):
        parser.error("--job-id must contain only letters, digits, _ or -")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
