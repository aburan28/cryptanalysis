#!/usr/bin/env python3
"""Exact pair-blocked chained-S3 plus signed complement scan on N83."""
import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
Q1507 = PARENT / "q20261012_n83_target_mid_priority"
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
Q1505 = PARENT / "q20261012_n83_deferred_y_scan"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BASE_MANIFEST = PARENT / "bases/n83_weight5_full_orbits.json"
TARGETS = {"selected": PARENT / "q20261011_wdsat_phase_restart/target.json",
           "holdout": PARENT / "q20261011_n83_selector_holdout/target.json"}
PAIR = re.compile(rb"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$", re.M)
sys.path[:0] = [str(PARENT), str(PARENT / "q20261011_operation_account"),
                str(ROOT / "ecc2k130/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]
from counted_onb import CountedOnb  # noqa: E402
from curves import Curve  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def blocked_system(raw, blocks):
    header, rest = raw.split(b"\n", 1)
    fields = header.split()
    assert fields[:2] == [b"p", b"cnf"] and len(fields) == 4
    variables, clauses = int(fields[2]), int(fields[3])
    assert variables == 65381
    lines = []
    next_aux = variables + 1
    count = 0
    for bits in blocks:
        assert len(bits) == 166 and set(bits) <= {"0", "1"}
        literals = [-(168 + i) if bit == "1" else 168 + i
                    for i, bit in enumerate(bits)]
        assert all((literal < 0) == (bits[abs(literal) - 168] == "1")
                   for literal in literals)
        start_aux = next_aux
        aux = next_aux
        next_aux += 1
        clauses3 = [[literals[0], literals[1], aux]]
        for literal in literals[2:-2]:
            following = next_aux
            next_aux += 1
            clauses3.append([-aux, literal, following])
            aux = following
        clauses3.append([-aux, literals[-2], literals[-1]])
        assert len(clauses3) == 164 and next_aux - start_aux == 163
        lines.extend(" ".join(map(str, clause)) + " 0\n" for clause in clauses3)
        count += len(clauses3)
    first_xor = rest.find(b"\nx")
    assert first_xor > 0
    cnf, xor = rest[:first_xor + 1], rest[first_xor + 1:]
    output = (b"p cnf " + str(next_aux - 1).encode() + b" " +
              str(clauses + count).encode() + b"\n" +
              cnf + "".join(lines).encode() + xor)
    return output


def pair_exhausted(row, folder):
    if row["sat"]["first_pair_bits"] is None:
        return False
    if not row["both_exact_base_usable"]:
        return True
    if len(row["scan_rows"]) != 4:
        return False
    for summary in row["scan_rows"]:
        s0, s1 = summary["signs"]
        scan = read(folder / f"scan_{s0}_{s1}" / "receipt.json")
        if scan["status"] != "COMPLETE" or scan["native_result"]["hits"] != 0:
            return False
    return True


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def sat_pair(binary, system, folder, protocol):
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    env = os.environ.copy()
    env.update(Q1469_ORDER_MODE=protocol["branch_order"],
               Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
               Q1481_LEAF_MASK=str(protocol["phase"]))
    started, reason = time.monotonic(), None
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen([str(binary), "-i", str(system)], stdout=out,
                                 stderr=err, env=env,
                                 preexec_fn=cpu_limit(
                                     protocol["cpu_soft_seconds_per_sat_attempt"],
                                     protocol["cpu_hard_seconds_per_sat_attempt"]))
        deadline = time.monotonic() + protocol["wall_seconds_per_sat_attempt"]
        sent_at = None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if sent_at is None:
                if PAIR.search(stderr.read_bytes()):
                    reason = "FIRST_PAIR_MARKER"
                elif now >= deadline:
                    reason = "WALL_CAP"
                if reason:
                    child.terminate()
                    sent_at = now
            elif now - sent_at > 5:
                child.kill()
            time.sleep(0.05)
    log = stderr.read_text(errors="replace")
    markers = [(int(a), int(b), int(c), d.decode()) for a, b, c, d in
               PAIR.findall(stderr.read_bytes())]
    assert len(markers) <= 1
    pair = markers[0] if markers else None
    if pair and "Q1458_SEARCH_START" in log:
        outcome = "FIRST_PAIR_TERMINATED"
    elif "Q1464_BRANCH_CAP 1048576" in log:
        outcome = "BRANCH_CAP_SEARCH_STARTED"
    elif reason == "WALL_CAP":
        outcome = "WALL_CAP_SEARCH_STARTED"
    elif child.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
        outcome = "CPU_CAP_SEARCH_STARTED"
    elif child.returncode == 0 and stdout.stat().st_size:
        outcome = "MODEL_REQUIRES_REPLAY"
    else:
        outcome = "PRODUCER_FAILURE"
    return {"status": outcome, "return_code": child.returncode,
            "termination_reason": reason,
            "search_started": "Q1458_SEARCH_START" in log,
            "order_marker_ok": f"Q1469_ORDER {protocol['branch_order']} 334" in log,
            "mask_marker_ok": f"Q1481_MASK {protocol['phase']} "
                f"{len(read(Q1488 / 'freeze.json')['mask_schedule'][str(protocol['phase'])]['flip_ids'])}" in log,
            "first_pair_branch": pair[0] if pair else None,
            "first_pair_cnf_calls": pair[1] if pair else None,
            "first_pair_xor_calls": pair[2] if pair else None,
            "first_pair_bits": pair[3] if pair else None,
            "first_pair_combined_calls": pair[1] + pair[2] if pair else None,
            "solver_wall_seconds_exploratory": time.monotonic() - started,
            "child_user_cpu_seconds": usage.ru_utime,
            "child_system_cpu_seconds": usage.ru_stime,
            "child_peak_rss_bytes_darwin": usage.ru_maxrss,
            "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}


def base_pair(bits, onb, curve, orbit, keys, order):
    leaves = []
    for i in (0, 1):
        coords = int(bits[83 * i:83 * (i + 1)][::-1], 2)
        onb.reset_counts()
        raw = curve.pointFromX(onb.fromCoords(coords)) if coords else None
        p = curve.mul(raw, 4) if raw is not None else None
        key = orbit.canonical(p)[0] if p is not None else None
        calls = onb.snapshot_counts()
        if p is not None:
            assert curve.onCurve(p) and curve.mul(p, order) is None
        leaves.append({"coords": coords, "weight": coords.bit_count(),
                       "rational_lift": raw is not None,
                       "exact_base_member": key in keys if key is not None else False,
                       "projected_orbit_key": key,
                       "filter_field_api_entries": sum(calls.values()),
                       "point": p})
    return leaves


def scan_pair(label, leaves, target, native, folder, protocol, onb, curve):
    rows = []
    for s0 in (1, -1):
        for s1 in (1, -1):
            p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
            p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
            complement = curve.add(target, curve.neg(curve.add(p0, p1)))
            assert complement is not None and curve.onCurve(complement)
            assert curve.add(curve.add(p0, p1), complement) == target
            args = [str(native), str(BASE), format(onb.toCoords(complement[0]), "x"),
                    format(onb.toCoords(complement[1]), "x"),
                    str(protocol["scan_pairs_per_complement"]), str(protocol["batch_pairs"])]
            cell = folder / f"scan_{s0}_{s1}"
            cell.mkdir()
            started = time.monotonic()
            try:
                proc = subprocess.run(args, text=True, capture_output=True,
                                      timeout=protocol["wall_seconds_per_complement"])
                status = "COMPLETE" if proc.returncode == 0 else "PROCESS_FAILURE"
                output, error = proc.stdout, proc.stderr
                code = proc.returncode
            except subprocess.TimeoutExpired as exc:
                status, output, error, code = (
                    "TIMEOUT", (exc.stdout or b"").decode(),
                    (exc.stderr or b"").decode(), None)
            (cell / "stdout.txt").write_text(output)
            (cell / "stderr.txt").write_text(error)
            lines = output.splitlines()
            result = json.loads(lines[-1]) if status == "COMPLETE" else None
            if result:
                assert result["actual_B"] == protocol["factor_base_actual_B"]
                assert result["scanned"] == protocol["factor_base_actual_B"]
            row = {"signs": [s0, s1], "status": status,
                   "return_code": code,
                   "complement_x_onb_hex": args[2],
                   "complement_y_onb_hex": args[3],
                   "native_result": result,
                   "native_hit_lines": lines[:-1] if result else [],
                   "wall_seconds_exploratory": time.monotonic() - started,
                   "stdout_sha256": sha(cell / "stdout.txt"),
                   "stderr_sha256": sha(cell / "stderr.txt"),
                   "batch_mul_calls_excluding_inversion_internals":
                       5 * protocol["scan_pairs_per_complement"] if result and
                       result["hits"] == 0 and result["exceptional_pairs"] == 0 else None}
            save(cell / "receipt.json", row)
            rows.append(row)
            print(label, folder.name, s0, s1, status,
                  result["hits"] if result else None, flush=True)
    return rows


def main():
    protocol = read(HERE / "protocol.json")
    frozen = read(Q1488 / "freeze.json")
    sat_build, native_build = (read(path) for path in
                               (HERE / "build_receipt.json", Q1505 / "build_receipt.json"))
    assert sha(Q1488 / "freeze.json") == protocol["source_sha256"]["q1488_freeze"]
    assert sha(BASE) == protocol["source_sha256"]["base"]
    sat, native = Path(sat_build["binary_path"]), Path(native_build["binary_path"])
    assert sha(sat) == sat_build["binary_sha256"]
    assert sha(native) == native_build["binary_sha256"]
    raw_base = BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = CountedOnb(83)
    curve, orbit = Curve(onb), OrbitKey(onb)
    order = int(read(BASE_MANIFEST)["curve"]["subgroup_order"])
    assert not (HERE / "result.json").exists()
    all_rows = []
    for label in ("selected", "holdout"):
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        target_fixture = read(TARGETS[label])
        assert target_fixture["workload_id"] == cell["workload_id"]
        target = tuple(target_fixture["public_target"])
        assert curve.onCurve(target)
        blocks = []
        for round_number in range(protocol["max_rounds_per_target"]):
            folder = HERE / "runs" / f"{label}_round{round_number}"
            if folder.exists():
                prior = read(folder / "receipt.json")
                assert prior["input"] == label and prior["round"] == round_number
                bits = prior["sat"]["first_pair_bits"]
                assert bits is not None and bits not in blocks
                if pair_exhausted(prior, folder):
                    blocks.append(bits)
                all_rows.append({"input": label, "round": round_number,
                                 "status": prior["sat"]["status"],
                                 "receipt_sha256": sha(folder / "receipt.json")})
                if not pair_exhausted(prior, folder):
                    break
                continue
            folder.mkdir(parents=True)
            system_bytes = blocked_system(raw, blocks)
            system = folder / "system.xcnf"
            system.write_bytes(system_bytes)
            attempt = sat_pair(sat, system, folder, protocol)
            system_sha256 = sha(system)
            (folder / "system.xcnf.gz").write_bytes(gzip.compress(system_bytes, mtime=0))
            system.unlink()
            assert attempt["order_marker_ok"] and attempt["mask_marker_ok"]
            bits = attempt["first_pair_bits"]
            if bits is not None:
                assert bits not in blocks
                leaves = base_pair(bits, onb, curve, orbit, keys, order)
                scan_rows = scan_pair(label, leaves, target, native, folder,
                                      protocol, onb, curve) if all(
                                          leaf["exact_base_member"] for leaf in leaves) else []
            else:
                leaves, scan_rows = [], []
            serialized_leaves = [{k: v for k, v in leaf.items() if k != "point"}
                                 for leaf in leaves]
            row = {"proposal_id": "Q1508", "candidate_id": None, "run_id": None,
                   "curve_id": protocol["curve_id"], "isogeny": "none",
                   "point_decomposition_stage_code": "PDP4hybrid",
                   "input": label, "workload_id": cell["workload_id"],
                   "round": round_number, "blocked_pair_count_before": round_number,
                   "blocked_pair_bits_sha256": [hashlib.sha256(x.encode()).hexdigest()
                                                for x in blocks],
                   "system_sha256": system_sha256, "sat": attempt,
                   "leaves": serialized_leaves,
                   "both_exact_base_usable": bool(leaves) and all(
                       x["exact_base_member"] for x in leaves),
                   "scan_rows": [{"signs": x["signs"], "status": x["status"],
                                  "receipt_sha256": sha(folder / f"scan_{x['signs'][0]}_{x['signs'][1]}" /
                                                        "receipt.json")}
                                 for x in scan_rows],
                   "complete_n83_decomposition_work_log2": None,
                   "complete_n131_solve_work_log2": None}
            save(folder / "receipt.json", row)
            if pair_exhausted(row, folder):
                blocks.append(bits)
            all_rows.append({"input": label, "round": round_number,
                             "status": attempt["status"],
                             "receipt_sha256": sha(folder / "receipt.json")})
            save(HERE / "result.partial.json", {"proposal_id": "Q1508",
                                                 "rows": all_rows})
            print(label, round_number, attempt["status"],
                  attempt["first_pair_combined_calls"],
                  row["both_exact_base_usable"], flush=True)
            if bits is None or not pair_exhausted(row, folder):
                break
    save(HERE / "result.json", {"proposal_id": "Q1508", "candidate_id": None,
                                "run_id": None, "curve_id": protocol["curve_id"],
                                "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
                                "protocol_sha256": sha(HERE / "protocol.json"),
                                "source_sha256": sha(Path(__file__)),
                                "rows": all_rows,
                                "complete_n83_decomposition_work_log2": None,
                                "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
