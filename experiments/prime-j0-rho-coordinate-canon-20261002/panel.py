"""Frozen panel of independent one-target rho solves, one fresh table each."""

import argparse
import hashlib
import json
import pathlib
import random
import statistics

from paired_rho import run


ORDERS = {"j0-36": 51131959441, "j0-37": 157632877033,
          "j0-46": 42111239174233}


def scalar_for(curve, index):
    key = f"j0-covariant-panel-v1:{curve}:{index}".encode()
    return 1 + int.from_bytes(hashlib.sha256(key).digest(), "big") % (ORDERS[curve] - 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=pathlib.Path, required=True)
    parser.add_argument("--candidate", type=pathlib.Path, required=True)
    parser.add_argument("--curve", choices=sorted(ORDERS), required=True)
    parser.add_argument("--targets", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.targets < 1:
        parser.error("--targets must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with args.output.open("w") as file:
        for index in range(args.targets):
            scalar = scalar_for(args.curve, index)
            order = ("reference", "candidate") if index % 2 == 0 else ("candidate", "reference")
            row = {"index": index, "curve": args.curve, "scalar_input": scalar,
                   "walk_seed": args.seed}
            for variant in order:
                binary = args.reference if variant == "reference" else args.candidate
                status, result = run(binary, args.curve, str(scalar), args.seed)
                row[variant] = result if result is not None else {"status": status}
                if result is None:
                    file.write(json.dumps(row, sort_keys=True) + "\n")
                    file.flush()
                    raise RuntimeError(f"{variant} target {index}: {status}")
            match = ("p", "b", "order", "base_x", "base_y", "target_x",
                     "target_y", "fixture_scalar", "seed")
            if any(row["reference"][field] != row["candidate"][field]
                   for field in match):
                raise ValueError(f"unpaired target {index}: {row}")
            file.write(json.dumps(row, sort_keys=True) + "\n")
            file.flush()
            results.append(row)
    ratios = [float(row["reference"]["online_ms"]) /
              float(row["candidate"]["online_ms"]) for row in results]
    cpu_ratios = [float(row["reference"]["cpu_ms"]) /
                  float(row["candidate"]["cpu_ms"]) for row in results]
    rng = random.Random(20261002)
    boot = sorted(statistics.median(ratios[rng.randrange(len(ratios))]
                                    for _ in ratios) for _ in range(10000))
    print(f"curve={args.curve} targets={len(ratios)} "
          f"median_paired_ratio={statistics.median(ratios):.6f} "
          f"bootstrap95=[{boot[250]:.6f},{boot[9749]:.6f}] "
          f"candidate_faster={sum(v > 1 for v in ratios)} "
          f"median_cpu_ratio={statistics.median(cpu_ratios):.6f} "
          f"ratios={[round(v, 3) for v in ratios]}")


if __name__ == "__main__":
    main()
