#!/usr/bin/env python3
"""Replay fixed-budget swapped and cycle-refined covers on one frozen panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-orbit-swap-20261011/replay_holdout.py"
SPEC = importlib.util.spec_from_file_location("cycle_replay_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
dual = parent.dual
BASE = ROOT / "prime-j0-orbit-swap-20261011/cover-swapped-rho0.bin"
NEW = HERE / "cover-cycle-refined.bin"


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
    base_raw, base_assign, base_seeds = load_cover(BASE)
    new_raw, new_assign, new_seeds = load_cover(NEW)
    assert digest(new_raw) == inputs["cover_sha256"]
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: i for i, node in enumerate(nodes)}
    counts = {"swapped": Counter(), "refined": Counter()}
    certificate = []
    improvements = regressions = ties = 0
    for index, text in enumerate(inputs["scalars_hex"]):
        scalar = int(text, 16)
        base = parent.recode(scalar, base_assign, base_seeds,
                             canonical, node_index)
        refined = parent.recode(scalar, new_assign, new_seeds,
                                canonical, node_index)
        for name, record in (("swapped", base), ("refined", refined)):
            counts[name]["active_rho"] += record["rho_terms"] != 0
            counts[name]["rho_terms"] += record["rho_terms"]
            counts[name]["nonzero_full_window"] += sum(
                row[2] != 0 for row in record["digits"])
            counts[name]["tau2_terms"] += sum(
                row[2] != 0 and row[3] == 2 for row in record["digits"])
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"],
                dual.screen.norm(record["terminal"]))
        improvements += base["rho_terms"] > 0 and refined["rho_terms"] == 0
        regressions += base["rho_terms"] == 0 and refined["rho_terms"] > 0
        ties += (base["rho_terms"] > 0) == (refined["rho_terms"] > 0)
        certificate.append(json.dumps({"index": index, "swapped": base,
                                       "refined": refined}, sort_keys=True,
                                      separators=(",", ":")))
    raw = ("\n".join(certificate) + "\n").encode()
    output.write_bytes(raw)
    receipt = {"schema": 1, "status": "screened", "cases": 4096,
               "source_sha256": digest(Path(__file__).read_bytes()),
               "input_sha256": digest(input_raw),
               "swapped_cover_sha256": digest(base_raw),
               "refined_cover_sha256": digest(new_raw),
               "certificate_sha256": digest(raw),
               "paired_activation_improvements": improvements,
               "paired_activation_regressions": regressions,
               "paired_activation_ties": ties,
               "swapped": dict(sorted(counts["swapped"].items())),
               "refined": dict(sorted(counts["refined"].items()))}
    assert improvements + regressions + ties == 4096
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in
                      ("swapped", "refined", "paired_activation_improvements",
                       "paired_activation_regressions")}, sort_keys=True))


if __name__ == "__main__":
    main()
