"""Build and check the packed Boolean-function matrix pilot; no timing claims."""
import argparse
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import subprocess

import matrix_reference as reference


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(binary, cases):
    payload = []
    for matrix, lanes in cases:
        payload.append(f"{len(matrix)} {len(matrix[0])} {lanes}\n")
        payload.append(" ".join(str(v) for row in matrix for v in row) + "\n")
    result = subprocess.run([str(binary)], input="".join(payload), text=True,
                            capture_output=True, check=True, timeout=180)
    assert not result.stderr, result.stderr
    answers = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(answers) == len(cases)
    return answers


def check_reference(matrix, lanes, answer, expected=None):
    rows, proof, pivots = expected or reference.shared_elimination(matrix, lanes)
    assert answer["rows"] == rows
    assert answer["proof"] == proof
    assert answer["pivots"] == pivots
    assert reference.identity_valid(matrix, answer["rows"], answer["proof"])


def span_rows(matrix, lane):
    # Separate canonical row-space computation, independent of pivot policy.
    rows = [sum(((v >> lane) & 1) << j for j, v in enumerate(row)) for row in matrix]
    basis = {}
    for row in rows:
        while row:
            lowest = row & -row
            if lowest not in basis:
                basis[lowest] = row
                break
            row ^= basis[lowest]
    for pivot in sorted(basis, reverse=True):
        for other in basis:
            if other != pivot and basis[other] & pivot:
                basis[other] ^= basis[pivot]
    return sorted(basis.items())


def controls():
    cases = []
    for lanes in (2, 4):
        for entries in itertools.product(range(1 << lanes), repeat=4):
            cases.append(([list(entries[:2]), list(entries[2:])], lanes))
    exhaustive = len(cases)
    rng = random.Random(2026093001)
    for lanes in (1, 2, 4, 8, 16):
        for _ in range(128):
            m, n = rng.randrange(1, 7), rng.randrange(1, 9)
            cases.append(([[rng.getrandbits(lanes) for _ in range(n)] for _ in range(m)], lanes))
        for m, n in ((3, 63), (3, 64), (3, 65), (65, 17), (3, 256), (512, 1)):
            cases.append(([[rng.getrandbits(lanes) for _ in range(n)] for _ in range(m)], lanes))
    cases += [([[14], [13]], 4), ([[1]], 2), ([[0, 0], [0, 0]], 4)]
    return cases, exhaustive


def main(output, compiler, affine_report):
    if output.exists():
        raise FileExistsError(output)
    source = Path(__file__).parent
    build = source / "build"
    build.mkdir(exist_ok=True)
    source_hashes = {p.name: digest(p) for p in (source / "packed_block.cpp", Path(__file__), Path(reference.__file__))}
    cases, exhaustive = controls()
    # Compute the Python policy once. Full native matrices/proofs must match,
    # while separate row-space and identity checks guard the shared policy.
    expected = []
    for matrix, lanes in cases:
        result = reference.shared_elimination(matrix, lanes)
        assert reference.identity_valid(matrix, result[0], result[1])
        for lane in range(lanes):
            assert span_rows(matrix, lane) == span_rows(result[0], lane)
        expected.append(result)
    actual = None
    if affine_report:
        actual = json.loads(gzip.decompress(affine_report.read_bytes()))
        assert actual["status"] == "PASS"
        assert actual["pilot_source_sha256"] == digest(Path(reference.__file__))
    report = {
        "schema": "native-block-sharing-cost-screen/1", "status": "PASS",
        "scope": "Exact matrix/proof checks and counted packed-word operations only; no solver, timing, GPU, or asymptotic claim.",
        "source_sha256": source_hashes,
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "compiler": subprocess.check_output([compiler, "--version"], text=True).strip(),
        "exhaustive_matrices": exhaustive, "random_matrices": 640,
        "word_boundary_and_extent_controls": 30, "exceptional_controls": 3,
        "builds": {}, "timing_eligible": False, "candidate_id": None, "online_speedup": None,
        "affine_report_sha256": digest(affine_report) if affine_report else None,
    }
    for variant, flags in (("optimized", ["-O3"]), ("ubsan", ["-O1", "-g", "-fsanitize=undefined", "-fno-sanitize-recover=all"])):
        binary = build / ("packed_block_" + variant)
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", *flags,
                   str(source / "packed_block.cpp"), "-o", str(binary)]
        subprocess.run(command, check=True)
        answer = native(binary, cases)
        for (matrix, lanes), got, want in zip(cases, answer, expected):
            check_reference(matrix, lanes, got, want)
        rejected = 0
        for invalid in ("0 1 4", "1 0 4", "513 1 4", "1 257 4", "1 1 0", "1 1 3", "1 1 32", "1 1 4 16", "1 1 4", "1", "bad"):
            bad = subprocess.run([str(binary)], input=invalid, text=True, capture_output=True)
            assert bad.returncode != 0 and not bad.stdout, (invalid, bad)
            rejected += 1
        entry = {"command": command, "binary_sha256": digest(binary), "matrices_checked": len(cases),
                 "invalid_inputs_rejected": rejected, "affine_blocks": []}
        if actual:
            for block in actual["records"]:
                matrix = block["input_matrix"]
                lanes = 1 << block["symbolic_bits"]
                scalar = [([[v >> lane & 1 for v in row] for row in matrix], 1) for lane in range(lanes)]
                block_answer, *lane_answers = native(binary, [(matrix, lanes)] + scalar)
                check_reference(matrix, lanes, block_answer,
                                (block["output_matrix"], block["proof"], block["pivot_columns"]))
                for (lane_matrix, _), lane_answer in zip(scalar, lane_answers):
                    check_reference(lane_matrix, 1, lane_answer)
                scalar_counts = {k: sum(a["counts"][k] for a in lane_answers) for k in block_answer["counts"]}
                row = {k: block[k] for k in ("name", "prefix_label", "prefix", "shared_pivots")}
                row.update(shared_counts=block_answer["counts"], scalar_counts=scalar_counts,
                           shared_matrix_and_proof_bytes=block_answer["matrix_bytes"] + block_answer["proof_bytes"],
                           scalar_matrix_and_proof_bytes=sum(a["matrix_bytes"] + a["proof_bytes"] for a in lane_answers),
                           shared_outputs_sha256=hashlib.sha256(json.dumps(block_answer, sort_keys=True).encode()).hexdigest())
                entry["affine_blocks"].append(row)
        report["builds"][variant] = entry
        print(variant, "PASS", len(cases), "matrices;", len(entry["affine_blocks"]), "affine blocks", flush=True)
    assert {p.name: digest(p) for p in (source / "packed_block.cpp", Path(__file__), Path(reference.__file__))} == source_hashes
    if actual:
        assert report["builds"]["optimized"]["affine_blocks"] == report["builds"]["ubsan"]["affine_blocks"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "c++"))
    parser.add_argument("--affine-report", type=Path)
    args = parser.parse_args()
    main(args.output, args.compiler, args.affine_report)
