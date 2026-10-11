"""Append exact disjoint-column source constraints to the frozen W18 XCNF."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010"
FOUR = GOAL / "n131_w18_four_preimage_20261010"
WIDTH = GOAL / "n131_w16_w18_sixpair_width_gate_20261010"
sys.path.insert(0, str(BASE))
import fixed_pair_circuit as pair  # noqa: E402
import matching  # noqa: E402


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    files = {"script": HERE / "overlay.py", "matching": HERE / "matching.py",
             "pair": BASE / "fixed_pair_circuit.py",
             "support": WIDTH / "support_w18.tsv",
             "input_xcnf": FOUR / "four_unpinned_constructed.xcnf",
             "input_build": FOUR / "unpinned_build_result.json"}
    protocol = json.loads((HERE / "overlay_protocol.json").read_text())
    assert protocol["source_sha256"] == {k: digest(v) for k, v in files.items()}
    columns = {int(a): int(b) for a, b in
               (line.split() for line in files["support"].read_text().splitlines())}
    edge_map = matching.edges(pair, columns)
    selected = set(matching.greedy_disjoint(edge_map))
    removed = sorted(set(edge_map) - selected)
    assert len(removed) == 64
    selectors = [[2 + slot*17 + bit for bit in range(17)] for slot in range(8)]
    extra_clauses, extra_xors = [], []
    for slot in selectors:
        for code in removed:
            extra_clauses.append([(-lit if code >> bit & 1 else lit)
                                  for bit, lit in enumerate(slot)])
    with files["input_xcnf"].open("r") as f:
        header = f.readline().split()
    assert header[:2] == ["p", "cnf"]
    original_vars, original_rows = int(header[2]), int(header[3])
    next_var = original_vars
    for i in range(8):
        for j in range(i):
            different = []
            for a, b in zip(selectors[i], selectors[j]):
                next_var += 1
                different.append(next_var)
                extra_xors.append([a, b, next_var])
            extra_clauses.append(different)
    assert len(extra_clauses) == 512+28 and len(extra_xors) == 476
    output = HERE / "matched_unpinned_constructed.xcnf"
    with files["input_xcnf"].open("r") as source, output.open("x") as target:
        source.readline()
        target.write("p cnf %d %d\n" %
                     (next_var, original_rows+len(extra_clauses)+len(extra_xors)))
        for block in iter(lambda: source.read(1024*1024), ""):
            target.write(block)
        for clause in extra_clauses:
            target.write(" ".join(map(str, clause)) + " 0\n")
        for xor in extra_xors:
            target.write("x-" + " ".join(map(str, xor)) + " 0\n")
    result = {"status": "PASS_MATCHING_OVERLAY_XCNF_BUILD",
              "candidate_id": None, "input_sha256": digest(files["input_xcnf"]),
              "output_sha256": digest(output), "output_bytes": output.stat().st_size,
              "input_variables": original_vars, "output_variables": next_var,
              "input_rows": original_rows,
              "output_rows": original_rows+len(extra_clauses)+len(extra_xors),
              "forbidden_codes_per_slot": len(removed),
              "code_disequalities": 28,
              "added_cnf_clauses": len(extra_clauses),
              "added_native_xor_rows": len(extra_xors),
              "selector_variables": selectors,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": digest(HERE / "overlay_protocol.json")}
    (HERE / "overlay_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({k: result[k] for k in ("status", "output_variables",
                                             "output_rows", "output_sha256")}))


if __name__ == "__main__":
    main()
