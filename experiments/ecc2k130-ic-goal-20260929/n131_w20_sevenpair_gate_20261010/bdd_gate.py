"""Build and exhaustively check the exact W20 fixed-seed source BDD."""

import hashlib
import json
import resource
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
WIDTH = 20


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_bdd(codes, bits):
    unique = {}
    nodes = {}

    def visit(subset, level):
        if not subset:
            return 0
        if len(subset) == 1 << (len(bits) - level):
            return 1
        if level == len(bits):
            return 1
        bit = len(bits) - level - 1
        low = [value for value in subset if not (value >> bit & 1)]
        high = [value for value in subset if value >> bit & 1]
        a, b = visit(low, level+1), visit(high, level+1)
        if a == b:
            return a
        key = (bit, a, b)
        if key not in unique:
            number = len(unique) + 2
            unique[key] = number
            nodes[number] = key
        return unique[key]

    return visit(sorted(codes), 0), nodes


def accepts(root, nodes, code):
    node = root
    while node >= 2:
        bit, low, high = nodes[node]
        node = high if code >> bit & 1 else low
    return node == 1


def main():
    protocol_path = HERE / "bdd_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "table": HERE / "support_w20.tsv",
             "count": HERE / "count_result_v2.json",
             "export_receipt": HERE / "export_receipt.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    count = json.loads(paths["count"].read_text())
    seed = count["selected_seed_mask"]
    pivot = seed.bit_length() - 1
    bits = [bit for bit in range(WIDTH) if bit != pivot]
    assert len(bits) == 19
    started = time.monotonic_ns()
    columns = {int(mask): int(column) for mask, column, shift in
               (line.split() for line in paths["table"].read_text().splitlines())}
    assert len(columns) == 524493
    valid = set()
    for mask, column in columns.items():
        other = mask ^ seed
        if mask < other and other in columns and column != columns[other]:
            code = sum(((mask >> bit) & 1) << index for index, bit in enumerate(bits))
            valid.add(code)
    assert len(valid) == count["selected_valid_unordered_pairs_per_slot"]
    loaded = time.monotonic_ns()
    root, nodes = build_bdd(valid, bits)
    built = time.monotonic_ns()
    accepted = 0
    for code in range(1 << len(bits)):
        expected = code in valid
        observed = accepts(root, nodes, code)
        assert observed == expected
        accepted += observed
    assert accepted == len(valid)
    checked = time.monotonic_ns()
    encoded = b"".join(code.to_bytes(3, "little") for code in sorted(valid))
    result = {"status": "PASS_EXACT_W20_PAIR_SOURCE_BDD",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "source_dimension": WIDTH, "fixed_seed_mask": seed,
              "pivot_bit": pivot, "selector_bits": bits,
              "selector_dimension": len(bits),
              "valid_codes": len(valid), "bdd_nodes": len(nodes),
              "bdd_root": root,
              "exhaustive_codes_checked": 1 << len(bits),
              "valid_code_sha256_u24le": hashlib.sha256(encoded).hexdigest(),
              "phase_ns": {"source_and_codes": loaded-started,
                           "bdd_build": built-loaded,
                           "exhaustive_truth_table": checked-built},
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "bdd_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "valid_codes": len(valid),
                      "bdd_nodes": len(nodes),
                      "truth_table": result["exhaustive_codes_checked"]}))


if __name__ == "__main__":
    main()
