"""Alternate full one-target rho solves across two build variants."""

import argparse
import pathlib
import random
import statistics
import subprocess


def run(binary, curve, scalar, seed):
    command = [str(binary.resolve()), curve, "1", scalar, str(seed)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "status=timeout verified=0", None
    result = proc.stdout.strip()
    if proc.returncode or result.count("\n") or "verified=1" not in result:
        return f"status=failed exit={proc.returncode} verified=0", None
    row = dict(token.split("=", 1) for token in result.split())
    return f"status=ok {result}", row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=pathlib.Path, required=True)
    parser.add_argument("--candidate", type=pathlib.Path, required=True)
    parser.add_argument("--curve", required=True)
    parser.add_argument("--scalar", required=True)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--pairs", type=int, default=24)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = {"reference": [], "candidate": []}
    with args.output.open("w") as file:
        for pair in range(1, args.pairs + 1):
            order = ("reference", "candidate") if pair % 2 else ("candidate", "reference")
            for variant in order:
                binary = args.reference if variant == "reference" else args.candidate
                result, row = run(binary, args.curve, args.scalar, args.seed)
                file.write(f"pair={pair} variant={variant} {result}\n")
                file.flush()
                if row is None:
                    raise RuntimeError(f"{variant} {args.curve} pair {pair}: {result}")
                rows[variant].append(row)
    match_fields = ("curve", "p", "b", "order", "base_x", "base_y",
                    "target_x", "target_y", "fixture_scalar", "seed")
    for field in match_fields:
        values = {row[field] for variant in rows.values() for row in variant}
        if len(values) != 1:
            raise ValueError(f"unmatched {field}: {values}")
    ref = [float(row["online_ms"]) for row in rows["reference"]]
    cand = [float(row["online_ms"]) for row in rows["candidate"]]
    ratios = [a / b for a, b in zip(ref, cand)]
    rng = random.Random(20261002)
    boot = sorted(statistics.median(ratios[rng.randrange(len(ratios))]
                                    for _ in ratios) for _ in range(10000))
    print(f"curve={args.curve} scalar={args.scalar} seed={args.seed} pairs={args.pairs} "
          f"reference_median_ms={statistics.median(ref):.6f} "
          f"candidate_median_ms={statistics.median(cand):.6f} "
          f"paired_ratio_median={statistics.median(ratios):.6f} "
          f"bootstrap95=[{boot[250]:.6f},{boot[9749]:.6f}] "
          f"candidate_faster={sum(v > 1 for v in ratios)} "
          f"reference_ops={rows['reference'][0]['ops']} "
          f"candidate_ops={rows['candidate'][0]['ops']}")


if __name__ == "__main__":
    main()
