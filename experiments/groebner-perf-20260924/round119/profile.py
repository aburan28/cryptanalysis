"""Pair complete scratch-buffer and bounded-bitset F4 queries."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASES = [f"pdp-12-seed-{seed}" for seed in range(1, 6)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    assert args.reps > 0 and args.timeout > 0
    root = HERE.parents[2]
    for path in HERE.glob("*.py"):
        relative = path.relative_to(root)
        assert path.read_bytes() == subprocess.check_output(
            ["git", "show", "HEAD:" + str(relative)], cwd=root)
    reference = json.loads(args.reference_report.read_text())
    assert reference["status"] in ("PASS", "RECORDED_PENDING_AUDIT")
    audit_path = args.reference_report.parent.parent / "audit.json"
    audit = json.loads(audit_path.read_text())
    assert audit["status"] == "PASS" and audit["rows"] == 52
    assert audit["native_binaries_loaded"] is False
    for round_number in (118, 119):
        directory = HERE.parent / f"round{round_number}"
        receipt = json.loads((directory / "build/receipt.json").read_text())
        for name, digest in receipt["binaries"].items():
            assert sha(directory / "build" / name) == digest
    references = {}
    for entry in reference["rows"]:
        if entry["name"] in CASES and entry["early_mode"] == 1 and not entry["sanitized"]:
            path = args.reference_report.parent / entry["result"]
            assert sha(path) == entry["sha256"]
            references[entry["name"]] = path
    assert set(references) == set(CASES)
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status="RUNNING", source_commit=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        source_sha256=sha(HERE / "profile.py"),
        reference_root=str(args.reference_root.resolve()),
        reference_report=str(args.reference_report),
        reference_sha256=sha(args.reference_report),
        reference_audit_sha256=sha(audit_path),
        repetitions=args.reps, rows=[], summary={},
        timing_eligible=False, qualified_speedup=None)
    save(args.output / "report.json", report)
    env = os.environ.copy()
    env["GROEBNER_PHASE_REFERENCE_ROOT"] = str(args.reference_root.resolve())
    env["GROEBNER_F4_REFERENCE_ROOT"] = str(args.reference_root.resolve())
    lock = Path("/private/tmp/cryptanalysis-overlap-evidence-20261003/local-heavy.lock"
                if sys.platform == "darwin" else "/tmp/groebner-local-heavy.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for repetition in range(-1, args.reps):
            cases = CASES[repetition % len(CASES):] + CASES[:repetition % len(CASES)]
            for case in cases:
                order = ("scratch", "bitset") if repetition % 2 == 0 else ("bitset", "scratch")
                pair = {}
                for arm in order:
                    tag = case + ("-warmup" if repetition < 0 else f"-r{repetition+1}") + "-" + arm
                    target = args.output / (tag + ".json")
                    script = HERE.parent / "round118/panel.py" if arm == "scratch" else HERE / "panel.py"
                    command = [sys.executable, str(script), "--case", case,
                               "--reference", str(references[case]), "--output", str(target)]
                    with (args.output / (tag + ".log")).open("w") as log:
                        try:
                            done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                                  timeout=args.timeout, env=env)
                            execution = "completed" if done.returncode == 0 else "process-failure"
                            exit_code = done.returncode
                        except subprocess.TimeoutExpired:
                            execution, exit_code = "timeout", None
                    row = dict(case=case, repetition=repetition+1, warmup=repetition < 0,
                               arm=arm, execution=execution, exit_code=exit_code,
                               log=tag + ".log")
                    if execution == "completed":
                        value = json.loads(target.read_text())
                        phase = next(a["native_phases"] for a in value["result"]["attempts"]
                                     if a["kind"] == "seeded-f4")
                        assert value["result"]["verified"] is True
                        assert value["result"]["reference_equations_and_curve_replay"] is True
                        row.update(result=target.name, sha256=sha(target),
                                   query_ns=value["wall_ns"], phase=phase,
                                   proof_sha256=value["reference_match"]["proof_sha256"],
                                   assignment=value["result"]["assignment"],
                                   basis=value["result"]["basis"],
                                   work=value["result"]["work"],
                                   check_work=value["result"]["check_work"])
                        pair[arm] = row
                    report["rows"].append(row)
                    save(args.output / "report.json", report)
                    print(tag, execution, flush=True)
                if len(pair) == 2:
                    assert all(pair["scratch"][key] == pair["bitset"][key]
                               for key in ("assignment", "basis", "proof_sha256", "work",
                                           "check_work"))
    if all(row["execution"] == "completed" for row in report["rows"]):
        for case in CASES:
            pairs = {}
            for row in report["rows"]:
                if row["case"] == case and not row["warmup"]:
                    pairs.setdefault(row["repetition"], {})[row["arm"]] = row
            assert len(pairs) == args.reps and all(len(pair) == 2 for pair in pairs.values())
            query_ratios = [pair["bitset"]["query_ns"] / pair["scratch"]["query_ns"]
                            for pair in pairs.values()]
            f4_ratios = [pair["bitset"]["phase"]["f4_ns"] / pair["scratch"]["phase"]["f4_ns"]
                         for pair in pairs.values()]
            work_ratios = [pair["bitset"]["work"] / pair["scratch"]["work"]
                           for pair in pairs.values()]
            assert len(set(work_ratios)) == 1
            report["summary"][case] = dict(
                n=len(pairs), median_bitset_over_scratch_query=statistics.median(query_ratios),
                median_bitset_over_scratch_f4=statistics.median(f4_ratios),
                bitset_over_scratch_work=work_ratios[0],
                query_ratios=query_ratios, f4_ratios=f4_ratios)
        report["status"] = "PASS"
    else:
        report["status"] = "INCOMPLETE"
    save(args.output / "report.json", report)
    print("F4_BITSET_PROFILE_" + report["status"], len(report["rows"]), flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
