"""Replay frozen hard queries with exact proofs and inner F4 phase clocks."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from inner_query import HERE, P, Query

sys.path.insert(0, str(P / "round111"))
sys.path.insert(0, str(P / "round108"))
spec = importlib.util.spec_from_file_location("leased_context114", P / "round111/panel.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
sys.path.insert(0, str(HERE.parent / "round113"))
from panel import assert_reference

CASES = [f"pdp-12-seed-{seed}" for seed in range(1, 6)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, row):
    path.write_text(json.dumps(row, indent=2) + "\n")


def worker(args):
    previous.Query = lambda **kwargs: Query(early_mode=1, **kwargs)
    context = previous.Context(args.case, args.sanitized)
    try:
        row = context.run(args.case, "matrix-block4")
    finally:
        for layout in context.layouts.values():
            layout.close()
    result = row["result"]
    if "proof" in result:
        owned = result.pop("proof")
        path = args.output.with_suffix(".gbp")
        path.write_bytes(owned.serialized())
        result["proof_artifact"] = dict(path=path.name, sha256=sha(path),
                                         bytes=path.stat().st_size,
                                         nodes=owned.nodes, outputs=owned.outputs)
    baseline = json.loads(args.reference.read_text())
    row["reference_match"] = assert_reference(row, baseline)
    row.update(name=args.case, sanitized=args.sanitized,
               fixture=context.cases[args.case], timing_eligible=False,
               qualified_speedup=None)
    save(args.output, row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--sanitized", action="store_true")
    args = parser.parse_args()
    if args.case:
        assert args.reference is not None
        worker(args)
        return
    assert args.reference_report is not None
    reference = json.loads(args.reference_report.read_text())
    assert reference["status"] in ("PASS", "RECORDED_PENDING_AUDIT")
    audit = args.reference_report.parent.parent / "audit.json"
    assert json.loads(audit.read_text())["status"] == "PASS"
    root = HERE.parents[2]
    for path in HERE.glob("*.py"):
        relative = path.relative_to(root)
        assert path.read_bytes() == subprocess.check_output(
            ["git", "show", "HEAD:" + str(relative)], cwd=root)
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status="RUNNING", source_commit=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip(),
        scripts={p.name: sha(p) for p in HERE.glob("*.py")},
        build=json.loads((HERE / "build/receipt.json").read_text()),
        reference_report=str(args.reference_report),
        reference_sha256=sha(args.reference_report), rows=[],
        reference_audit=str(audit), reference_audit_sha256=sha(audit),
        timing_eligible=False, qualified_speedup=None)
    save(args.output / "report.json", report)
    for sanitized in (False, True):
        for case in CASES:
            name = case + "-early1" + ("-ubsan" if sanitized else "")
            target = args.output / (name + ".json")
            command = [sys.executable, str(HERE / "panel.py"), "--case", case,
                       "--reference", str(args.reference_report.parent / (name + ".json")),
                       "--output", str(target)]
            if sanitized:
                command.append("--sanitized")
            with target.with_suffix(".log").open("w") as log:
                try:
                    done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=90, env=os.environ.copy())
                    row = dict(name=case, sanitized=sanitized, exit_code=done.returncode,
                               execution="completed" if done.returncode == 0 else "process-failure")
                except subprocess.TimeoutExpired:
                    row = dict(name=case, sanitized=sanitized, execution="timeout")
            if row["execution"] == "completed":
                row.update(result=target.name, sha256=sha(target))
            report["rows"].append(row)
            save(args.output / "report.json", report)
            print(name, row["execution"], flush=True)
    report["status"] = "PASS" if all(row["execution"] == "completed" for row in report["rows"]) else "INCOMPLETE"
    save(args.output / "report.json", report)
    print("F4_INNER_PANEL_" + report["status"], len(report["rows"]), flush=True)


if __name__ == "__main__":
    main()
