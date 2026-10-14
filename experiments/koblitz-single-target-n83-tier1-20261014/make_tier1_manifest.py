#!/usr/bin/env python3
"""Freeze the three Tier 1 panels of the N83 one-target IC/rho protocol as isolated_bench manifests.

Panel A: frozen Q0, strong rho rung 3 (reference) vs cached IC (candidate),
eight interleaved pairs. Panel B: the beat's first 16 public points, one pair
each, order alternating across points. Panel C: Q0, legacy packed rho vs
cached IC, eight interleaved pairs. isolated_bench reports
reference/candidate, so every pair ratio is rho_online_ms / ic_online_ms.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from restore_crypto_source import ensure_snapshot

EXPERIMENT = Path("experiments/koblitz-single-target-n83-tier1-20261014")
ALTERNATE = [["reference", "candidate"], ["candidate", "reference"]] * 4


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--bin-dir", required=True, type=Path)
    parser.add_argument("--log-table", required=True, type=Path)
    parser.add_argument("--precompute-receipt", required=True, type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", required=True, type=int)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--allocation-receipt", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--panels", default="A,B,C")
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    here = root / EXPERIMENT
    protocol_path = here / "tier1_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    allocation = args.allocation_receipt.resolve(strict=True)
    receipt = json.loads(allocation.read_text())
    if receipt.get("provider") != args.provider or receipt.get("instance_id") != args.instance_id:
        raise ValueError("allocation receipt does not match provider and instance ID")
    precompute = json.loads(args.precompute_receipt.read_text())
    table = args.log_table.resolve(strict=True)
    if precompute.get("status") != "PASS" or precompute.get("table_sha256") != digest(table):
        raise ValueError("the factor-log table is not the verified precompute output")
    bound = protocol["precompute"].get("committed_log_table_sha256")
    if bound and bound != digest(table):
        raise ValueError("the factor-log table differs from the committed table")
    if (protocol["measurement_tier"] != "tier1_instance" or
            protocol["panels"]["A"]["repetitions"] != 8 or protocol["panels"]["A"]["pair_order"] != ALTERNATE or
            protocol["panels"]["C"]["repetitions"] != 8 or protocol["panels"]["C"]["pair_order"] != ALTERNATE or
            protocol["panels"]["B"]["targets"] < 5 or protocol["panels"]["B"]["repetitions"] != 1):
        raise ValueError("panel design differs from the frozen protocol")

    snapshot = ensure_snapshot()
    targets = json.loads((here / protocol["inputs"]["targets_file"]).read_text())
    base = snapshot / protocol["inputs"]["base"]
    python = args.python.resolve(strict=True)
    bins = {name: (args.bin_dir / binary).resolve(strict=True)
            for name, binary in protocol["build"]["binaries"].items()}
    wrapper = here / "arm.py"

    def arm(name, panel, point, seed=0):
        command = [str(python), str(wrapper), "--arm", name, "--panel", panel,
                   "--binary", str(bins[name]), "--point", "%s,%s" % tuple(point),
                   "--seed", str(seed)]
        if name == "ic":
            command += ["--base", str(base), "--base-hash", protocol["inputs"]["base_hash"],
                        "--log-table", str(table), "--rank-seed", str(protocol["precompute"]["rank_seed"])]
        return command

    q0 = targets["q0"]["point"]
    panels = {
        "A": [{"id": "A-q0", "reference": arm("rho", "A", q0, protocol["panels"]["A"]["rho_seed"]),
               "candidate": arm("ic", "A", q0)}],
        "B": [{"id": "B-w%03d" % entry["seed"],
               "reference": arm("rho", "B", entry["point"], 830000 + entry["seed"]),
               "candidate": arm("ic", "B", entry["point"])}
              for entry in targets["panel_b"]["points"][:protocol["panels"]["B"]["targets"]]],
        "C": [{"id": "C-q0", "reference": arm("rho_legacy", "C", q0, protocol["panels"]["C"]["rho_seed"]),
               "candidate": arm("ic", "C", q0)}],
    }
    artifacts = sorted({str(p) for p in [
        python, wrapper, protocol_path, here / "make_tier1_manifest.py", here / "restore_crypto_source.py",
        here / "ic_log_cache.patch", here / "Cargo.toml", here / "Cargo.lock",
        here / protocol["inputs"]["targets_file"], base, table, allocation,
        args.precompute_receipt.resolve(strict=True)] + list(bins.values())})
    boundary = (protocol["clocks"]["ic"]["online_start"] + " -> " + protocol["clocks"]["ic"]["online_stop"] +
                " (IC); " + protocol["clocks"]["rho"]["online_start"] + " -> " +
                protocol["clocks"]["rho"]["online_stop"] + " (rho). Wrapper start-up, input writing and "
                "checks are outside both producer clocks.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in args.panels.split(","):
        spec = protocol["panels"][name]
        manifest = {
            "schema": 1,
            "measurement_tier": "tier1_instance",
            "allocation": {"provider": args.provider, "instance_id": args.instance_id,
                           "receipt": str(allocation)},
            "workdir": str(root),
            "isolation": {"cpus": args.cpus, "execution_cpu": args.execution_cpu},
            "measurement_boundary": boundary if name != "C" else
                boundary.replace(" (rho).", " (rho, strong); legacy packed rho: total_ms = target-dependent "
                                 "jump setup + walk + validation."),
            "pair_fields": protocol["pair_fields"],
            "result_field": protocol["result_field"],
            "cases": panels[name],
            "repetitions": spec["repetitions"],
            "timeout_s": spec["timeout_s_per_arm"],
            "artifacts": artifacts,
        }
        output = args.output_dir / ("manifest_%s.json" % name)
        with output.open("x") as stream:
            json.dump(manifest, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        written.append(str(output))
    print("\n".join(written))


if __name__ == "__main__":
    main()
