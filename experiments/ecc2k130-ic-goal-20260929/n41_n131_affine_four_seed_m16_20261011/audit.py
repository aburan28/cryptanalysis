"""Independent source-count and retained bounded-query receipt audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rank_low(values):
    pivots = {}
    for value in values:
        while value:
            low = value & -value
            if low not in pivots:
                pivots[low] = value
                break
            value ^= pivots[low]
    return len(pivots)


def square(value, degree, taps):
    raw = sum(1 << (2*bit) for bit in range(degree) if value >> bit & 1)
    modulus = (1 << degree) | sum(1 << bit for bit in taps)
    while raw.bit_length() > degree:
        raw ^= modulus << (raw.bit_length()-degree-1)
    return raw


def rotated_rank_panel(degree, dimension, taps, rotations):
    rows = []
    for rotation in rotations:
        one = []
        for bit in range(1, dimension+1):
            value = 1 << bit
            for _ in range(rotation):
                value = square(value, degree, taps)
            one.append(value)
        rows.append(one)
    ranks = [rank_low(rows[i]+rows[j]) for i in range(8) for j in range(i+1, 8)]
    assert ranks == [2*dimension]*28
    return ranks


protocol = json.loads((HERE / "protocol.json").read_text())
support = json.loads((HERE / "support_result.json").read_text())
control = json.loads((HERE / "control_result.json").read_text())
query = json.loads((HERE / "query_result.json").read_text())
fixture = json.loads((HERE / "control_fixture.json").read_text())
public = json.loads((ROOT / "n41_transport_cubic_s8_20261011" / "fixture.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_N41_M16_CONTROL_AND_QUERY"
assert support["status"] == "EXACT_AFFINE_FOUR_SEED_SOURCE_CENSUS"
assert fixture["status"] == "PASS_N41_AFFINE_FOUR_SEED_M16_GROUP_CONTROL"
assert control["protocol_sha256"] == query["protocol_sha256"] == sha(HERE / "protocol.json")
assert control["control_fixture_sha256"] == sha(HERE / "control_fixture.json")
assert fixture["source_sha256"]["prepare_sage.py"] == sha(HERE / "prepare_sage.py")
assert fixture["source_sha256"]["sage_runtime_info"] == sha(HERE / "sage_runtime_info.json")
assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
assert protocol["source_sha256"]["run.py"] == sha(HERE / "run.py")
assert protocol["source_sha256"]["circuit.py"] == sha(HERE / "circuit.py")
assert protocol["source_sha256"]["support.py"] == sha(HERE / "support.py")
assert protocol["source_sha256"]["support_result.json"] == sha(HERE / "support_result.json")
assert protocol["source_sha256"]["prepare_sage.py"] == sha(HERE / "prepare_sage.py")
assert support["source_sha256"]["support.py"] == sha(HERE / "support.py")
assert support["source_sha256"]["n41_fixture"] == sha(ROOT / "n41_transport_cubic_s8_20261011" / "fixture.json")
assert support["source_sha256"]["n131_support"] == sha(ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv")
columns41 = {int(k): int(v) for k, v in public["mask_columns"].items()}
columns131 = {int(a): int(b) for a, b in
              (line.split() for line in (ROOT / "n131_w16_w18_sixpair_width_gate_20261010" /
                "support_w18.tsv").read_text().splitlines())}
counts = {}
for label, columns, seeds in (("n41", columns41, (32, 33, 34, 35)),
                               ("n131", columns131, (212, 213, 214, 215))):
    counts[label] = {}
    for seed in seeds:
        count = 0
        for left in columns:
            right = left ^ seed
            if right in columns and columns[left] != columns[right]:
                count += 1
        assert count % 2 == 0
        counts[label][str(seed)] = count//2
    assert counts[label] == support[label]["per_seed_unordered_pairs"]
    total = sum(counts[label].values())
    assert total == support[label]["unordered_pairs_per_slot"]
    assert (4*total)**8 == int(support[label]["labeled_eight_slot_tuple_ceiling"])
    assert support[label]["factor_base_B_eight_windows"] == 16*len(columns)
    assert support[label]["folded_columns_K"] == len(set(columns.values()))
rank41 = rotated_rank_panel(41, 6, (0, 3), range(0, 40, 5))
rank131 = rotated_rank_panel(131, 18, (0, 1, 2, 13), range(0, 128, 16))
assert min(rank41) == support["n41"]["rotated_subspace_pair_rank"]
assert min(rank131) == support["n131"]["rotated_subspace_pair_rank"]
assert all((fixture["masks"][2*i] ^ fixture["masks"][2*i+1]) in (32, 33, 34, 35)
           for i in range(8))
assert len(set(fixture["source_columns"])) == 16
assert len(fixture["branch_bits"]) == 15
assert control["status"] == "PASS_COMPLETE_N41_M16_CIRCUIT_ASSIGNMENT"
assert control["assignment_check"] == {"clauses": 51790, "native_xor_rows": 10663}
assert control["formula_sha256"] == sha(HERE / "control.xcnf")
assert query["formula"]["sha256"] == sha(HERE / "public.xcnf")
assert query["public_target"] == protocol["public_target"]
assert query["status"] == "BOUNDED_UNKNOWN" and query["stop_reason"] == "PARENT_CAP"
assert query["solver_started"] and query["solver_seconds"] >= protocol["solver_cap_seconds"]
assert query["peak_combined_rss_bytes"] < protocol["combined_rss_cap_bytes"]
assert query["stdout_sha256"] == sha(HERE / "solver.stdout.txt")
assert query["stderr_sha256"] == sha(HERE / "solver.stderr.txt")
stdout = (HERE / "solver.stdout.txt").read_text()
assert "s SATISFIABLE" not in stdout and "s UNSATISFIABLE" not in stdout
restart_rows = sum(line.startswith("c rst ") for line in stdout.splitlines())
assert restart_rows > 0
phase_sum = (query["construction_seconds"] + query["write_seconds"] +
             query["solver_seconds"] + query["post_seconds"] +
             query["unallocated_seconds"])
assert abs(phase_sum-query["total_seconds"]) < 1e-9
result = {"status": "PASS_N41_M16_FOUR_SEED_BOUNDED_AUDIT",
          "per_seed_pair_counts": counts,
          "n41_rotated_pair_ranks": sorted(set(rank41)),
          "n131_rotated_pair_ranks": sorted(set(rank131)),
          "control_formula_sha256": control["formula_sha256"],
          "public_formula_sha256": query["formula"]["sha256"],
          "restart_rows": restart_rows, "phase_sum_seconds": phase_sum,
          "protocol_sha256": sha(HERE / "protocol.json")}
with (HERE / "audit_result.json").open("x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps({"status": result["status"], "restart_rows": restart_rows}))
