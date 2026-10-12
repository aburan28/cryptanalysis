#!/usr/bin/env python3
"""Bounded exact W<=5 quotient pair search on two ordinary N83 points."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
BASE = ROOT / "bases/n83_weight5_full_point_orbits.bin"
SOURCE = ROOT / "q20261012_n83_blocked_pair_handoff"
sys.path[:0] = [str(REPO / "ecc2k130/codegen")]
from field import Onb  # noqa: E402
from curves import Curve  # noqa: E402

BINARY = Path("/Volumes/SSD990/llm/tmp/q1529-native-w5-query")
EXPECTED_BASE_SHA = "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"
TARGETS = {
    "selected": ROOT / "q20261011_wdsat_phase_restart/target.json",
    "holdout": ROOT / "q20261011_n83_selector_holdout/target.json",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def compact(onb: Onb, value: int) -> int:
    return onb.toCoords(value)


def point_from_record(onb: Onb, record: bytes) -> tuple[int, int]:
    assert len(record) == 21
    bits = int.from_bytes(record, "little")
    order = []
    j = 1
    for _ in range(83):
        order.append(j - 1)
        j = min(2 * j % 167, 167 - 2 * j % 167)
    assert j == 1 and len(set(order)) == 83
    xy = []
    for start in (83, 0):
        value = sum(((bits >> (start + i)) & 1) << order[i]
                    for i in range(83))
        xy.append(onb.fromCoords(value))
    return tuple(xy)


def run_cell(label: str, target: tuple[int, int], table: int, query: int,
             bits: int, hashes: int, rep_batch: int, workers: int = 1) -> dict:
    name = f"{label}_t{table}_q{query}_b{bits}_h{hashes}_r{rep_batch}_w{workers}"
    folder = HERE / "runs" / name
    if (folder / "receipt.json").exists():
        prior = json.loads((folder / "receipt.json").read_text())
        assert prior["status"] == "COMPLETE"
        assert prior["stdout_sha256"] == sha(folder / "stdout.txt")
        assert prior["stderr_sha256"] == sha(folder / "stderr.txt")
        return prior
    folder.mkdir(parents=True, exist_ok=False)
    onb = Onb(83)
    args = [str(BINARY), str(BASE), *(format(compact(onb, v), "x") for v in target),
            str(table), str(query), "1024", "1", "0", "1", "0",
            str(bits), str(hashes), "0", "0", str(workers), str(rep_batch)]
    start = time.monotonic()
    try:
        process = subprocess.run(args, capture_output=True, timeout=120, check=False)
        status = "COMPLETE" if process.returncode == 0 else "PROCESS_FAILURE"
        output, error, returncode = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as exc:
        status = "WALL_CAP"
        output, error, returncode = exc.stdout or b"", exc.stderr or b"", None
    (folder / "stdout.txt").write_bytes(output)
    (folder / "stderr.txt").write_bytes(error)
    native = json.loads(output) if status == "COMPLETE" else None
    receipt = {
        "proposal_id": "Q1529", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "stage": "PDP4mitm", "label": label,
        "workload_id": ("2eb250a29072" if label == "selected" else
                        "394256b9f901" if label == "holdout" else None),
        "status": status, "command": args, "return_code": returncode,
        "wall_seconds_exploratory": time.monotonic() - start,
        "stdout_sha256": sha(folder / "stdout.txt"),
        "stderr_sha256": sha(folder / "stderr.txt"), "native": native,
        "full_n131_solve_work_log2": None,
    }
    save(folder / "receipt.json", receipt)
    return receipt


def main() -> None:
    assert sha(BASE) == EXPECTED_BASE_SHA
    assert BASE.stat().st_size == 186612 * 21
    assert BINARY.is_file()
    onb = Onb(83)
    curve = Curve(onb)
    targets = {name: tuple(json.loads(path.read_text())["public_target"])
               for name, path in TARGETS.items()}
    assert all(curve.onCurve(point) for point in targets.values())
    with BASE.open("rb") as stream:
        p, q = (point_from_record(onb, stream.read(21)) for _ in range(2))
    assert curve.onCurve(p) and curve.onCurve(q)
    planted = curve.dbl(curve.add(p, q))
    assert curve.onCurve(planted)
    metadata = {
        "proposal_id": "Q1529", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "base_B": 30977592, "folded_K": 186612,
        "base_sha256": sha(BASE), "binary_sha256": sha(BINARY),
        "source_sha256": {name: sha(HERE / name) for name in
                          ("native_w5_query.cpp", "native_n83_bloom_core.hpp",
                           "native_n83_pairs.cpp", "eccF83.h")},
        "target_sha256": {name: sha(path) for name, path in TARGETS.items()},
        "target_xy_compact_hex": {name: [format(compact(onb, v), "x") for v in point]
                                  for name, point in targets.items()},
        "control_xy_compact_hex": [format(compact(onb, v), "x") for v in planted],
        "host_isolation": None, "full_n131_solve_work_log2": None,
    }
    save(HERE / "protocol.json", metadata)
    cells = [("control", planted, 1, 1, 16, 4, 1, 1)]
    for label, point in targets.items():
        cells.extend((label, point, 1 << 18, 1 << 17, bits, hashes, rep, 1)
                     for bits, hashes, rep in ((8, 3, 8), (16, 4, 8),
                                               (32, 6, 8), (16, 4, 24)))
    cells.extend(("selected", targets["selected"], 1 << 18, 1 << 20,
                  bits, hashes, 8, workers)
                 for bits, hashes, workers in ((8, 3, 1), (8, 3, 4),
                                               (16, 4, 4)))
    cells.append(("holdout", targets["holdout"], 1 << 18, 1 << 20,
                  8, 3, 8, 4))
    results = []
    for cell in cells:
        receipt = run_cell(*cell)
        results.append({"label": receipt["label"], "status": receipt["status"],
                        "native": receipt["native"],
                        "receipt_sha256": sha(HERE / "runs" /
                                              f"{cell[0]}_t{cell[2]}_q{cell[3]}_b{cell[4]}_h{cell[5]}_r{cell[6]}_w{cell[7]}" /
                                              "receipt.json")})
        native = receipt["native"] or {}
        print(cell[0], cell[4:7], receipt["status"],
              native.get("exact_hit_queries"), native.get("query_seconds"), flush=True)
        save(HERE / "result.partial.json", {"rows": results})
        if receipt["status"] != "COMPLETE":
            break
        if cell[0] == "control":
            assert native["exact_hit_queries"] >= 1, "positive control failed"
    save(HERE / "result.json", {**metadata, "rows": results})


if __name__ == "__main__":
    main()
