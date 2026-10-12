#!/usr/bin/env python3
"""Replay swapped and priority orbit covers on one frozen scalar panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-carry-aware-v2-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("orbit_swap_replay_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
dual = parent.dual
OLD = ROOT / "prime-j0-dual-orbit-20261011/cover-priority-rho0.bin"
NEW = HERE / "cover-swapped-rho0.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def load_cover(path):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    assignments = [divmod(value, 16) for (value,) in
                   struct.iter_unpack("<I", raw[20:offset])]
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    return raw, assignments, seeds


def recode(scalar, assignments, seeds, canonical, node_index):
    a, b = dual.screen.representative(scalar % dual.screen.ORDER)
    start = a, b
    assert (a + b * dual.LAMBDA_TAU - scalar) % dual.screen.ORDER == 0
    path = []
    place = 1
    reconstructed = [0, 0]
    rho_terms = 0
    for _ in range(dual.WINDOWS):
        node = canonical[(a % dual.RADIX) * dual.RADIX + b % dual.RADIX]
        seed_id, map_id = assignments[node_index[node]]
        mapped = dual.mapped(seeds[seed_id], map_id)
        choices = [(unit, digit) for unit, digit in enumerate(
            dual.screen.units(mapped))
            if digit[0] % dual.RADIX == a % dual.RADIX
            and digit[1] % dual.RADIX == b % dual.RADIX]
        assert choices
        unit, digit = choices[0]
        assert dual.screen.norm(digit) <= dual.NORM_LIMIT
        path.append([digit[0], digit[1], seed_id, map_id, unit])
        reconstructed[0] += place * digit[0]
        reconstructed[1] += place * digit[1]
        a, b = (a - digit[0]) // dual.RADIX, (b - digit[1]) // dual.RADIX
        place *= dual.RADIX
        rho_terms += seed_id != 0 and map_id == 3
    assert dual.screen.norm((a, b)) < dual.TERMINAL_BOUND ** 2
    reconstructed[0] += place * a
    reconstructed[1] += place * b
    assert tuple(reconstructed) == start
    return {"digits": path, "terminal": [a, b], "rho_terms": rho_terms}


def main():
    output = HERE / "holdout-paths.jsonl"
    receipt_path = HERE / "holdout-screen.json"
    if output.exists() or receipt_path.exists():
        raise SystemExit("holdout output already exists")
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    inputs = json.loads(input_raw)
    assert inputs["count"] == 4096
    assert inputs["candidate_source_sha256"]["replay_holdout.py"] == \
        digest(Path(__file__).read_bytes())
    old_raw, old_assign, old_seeds = load_cover(OLD)
    new_raw, new_assign, new_seeds = load_cover(NEW)
    assert digest(new_raw) == inputs["cover_sha256"]
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    counts = {"priority": Counter(), "swapped": Counter()}
    improvements = regressions = ties = 0
    certificate = []
    for index, text in enumerate(inputs["scalars_hex"]):
        scalar = int(text, 16)
        old = recode(scalar, old_assign, old_seeds, canonical, node_index)
        new = recode(scalar, new_assign, new_seeds, canonical, node_index)
        for name, record in (("priority", old), ("swapped", new)):
            counts[name]["active_rho"] += record["rho_terms"] != 0
            counts[name]["rho_terms"] += record["rho_terms"]
            counts[name]["nonzero_full_window"] += sum(
                row[2] != 0 for row in record["digits"])
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"],
                dual.screen.norm(record["terminal"]))
        improvements += old["rho_terms"] > 0 and new["rho_terms"] == 0
        regressions += old["rho_terms"] == 0 and new["rho_terms"] > 0
        ties += (old["rho_terms"] > 0) == (new["rho_terms"] > 0)
        certificate.append(json.dumps({"index": index, "priority": old,
                                       "swapped": new}, sort_keys=True,
                                      separators=(",", ":")))
    raw = ("\n".join(certificate) + "\n").encode()
    output.write_bytes(raw)
    result = {"schema": 1, "status": "screened", "cases": 4096,
              "source_sha256": digest(Path(__file__).read_bytes()),
              "input_sha256": digest(input_raw),
              "priority_cover_sha256": digest(old_raw),
              "swapped_cover_sha256": digest(new_raw),
              "certificate_sha256": digest(raw),
              "paired_activation_improvements": improvements,
              "paired_activation_regressions": regressions,
              "paired_activation_ties": ties,
              "priority": dict(sorted(counts["priority"].items())),
              "swapped": dict(sorted(counts["swapped"].items()))}
    assert improvements + regressions + ties == 4096
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in
                      ("priority", "swapped", "paired_activation_improvements",
                       "paired_activation_regressions")}, sort_keys=True))


if __name__ == "__main__":
    main()
