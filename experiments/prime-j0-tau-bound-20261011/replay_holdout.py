#!/usr/bin/env python3
"""Replay exact tau-only and fixed-budget swapped covers on one panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-orbit-swap-20261011/replay_holdout.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_replay_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
dual = parent.dual
BASE = ROOT / "prime-j0-orbit-swap-20261011/cover-swapped-rho0.bin"
TAU = HERE / "cover-tau-exact.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def load_cover(path, expected_count, expected_mask):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, expected_count, expected_mask)
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
    base_raw, base_assign, base_seeds = load_cover(BASE, 67_338, 15)
    tau_raw, tau_assign, tau_seeds = load_cover(TAU, 73_417, 7)
    assert digest(tau_raw) == inputs["cover_sha256"]
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    counts = {"swapped": Counter(), "tau_exact": Counter()}
    certificate = []
    for index, text in enumerate(inputs["scalars_hex"]):
        scalar = int(text, 16)
        base = parent.recode(scalar, base_assign, base_seeds,
                             canonical, node_index)
        tau = parent.recode(scalar, tau_assign, tau_seeds,
                            canonical, node_index)
        assert tau["rho_terms"] == 0
        for name, record in (("swapped", base), ("tau_exact", tau)):
            counts[name]["active_rho"] += record["rho_terms"] != 0
            counts[name]["rho_terms"] += record["rho_terms"]
            counts[name]["nonzero_full_window"] += sum(
                row[2] != 0 for row in record["digits"])
            counts[name]["tau2_terms"] += sum(
                row[2] != 0 and row[3] == 2 for row in record["digits"])
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"],
                dual.screen.norm(record["terminal"]))
        certificate.append(json.dumps({"index": index, "swapped": base,
                                       "tau_exact": tau}, sort_keys=True,
                                      separators=(",", ":")))
    raw = ("\n".join(certificate) + "\n").encode()
    output.write_bytes(raw)
    result = {"schema": 1, "status": "screened", "cases": 4096,
              "source_sha256": digest(Path(__file__).read_bytes()),
              "input_sha256": digest(input_raw),
              "swapped_cover_sha256": digest(base_raw),
              "tau_cover_sha256": digest(tau_raw),
              "certificate_sha256": digest(raw),
              "swapped": dict(sorted(counts["swapped"].items())),
              "tau_exact": dict(sorted(counts["tau_exact"].items()))}
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"swapped": result["swapped"],
                      "tau_exact": result["tau_exact"]}, sort_keys=True))


if __name__ == "__main__":
    main()
