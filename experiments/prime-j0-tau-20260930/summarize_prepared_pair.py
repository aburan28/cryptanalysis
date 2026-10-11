"""Summarize verified, paired one-target rho timings from saved raw rows."""

import argparse
import pathlib
import random
import statistics


def load(path, expected_curve, expected_width):
    rows = []
    for line in path.read_text().splitlines():
        row = dict(token.split("=", 1) for token in line.split())
        if row["curve"] != expected_curve or int(row["width"]) != expected_width:
            raise ValueError(f"unexpected curve or width in {path}")
        if row["verified"] != "1":
            raise ValueError(f"unverified solve in {path}")
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=pathlib.Path)
    parser.add_argument("--curves", nargs="+", default=("glv-j0-26", "glv-j0-32"))
    args = parser.parse_args()
    rng = random.Random(20261001)
    for curve in args.curves:
        rows = {
            width: load(
                args.directory / f"rho_{curve}_width{width}_prepared_pair.txt",
                curve,
                width,
            )
            for width in (2, 4)
        }
        if len(rows[2]) != len(rows[4]) or not rows[2]:
            raise ValueError("missing paired rows")
        for width in (2, 4):
            first = rows[width][0]
            for index, row in enumerate(rows[width], 1):
                if int(row["pair"]) != index:
                    raise ValueError(f"missing or duplicate pair in width {width}")
                for field in ("curve", "p", "b", "order", "base_x", "base_y",
                              "target_x", "target_y", "fixture_scalar", "seed"):
                    if field in first and row[field] != first[field]:
                        raise ValueError(f"changing {field} in width {width}")
        for left, right in zip(rows[2], rows[4]):
            for field in ("pair", "p", "b", "order", "base_x", "base_y",
                          "target_x", "target_y", "fixture_scalar", "seed"):
                if field not in left and field not in right:
                    continue
                if left[field] != right[field]:
                    raise ValueError(f"unpaired {field}: {left} versus {right}")
        times = {width: [float(row["online_ms"]) for row in rows[width]]
                 for width in (2, 4)}
        ratios = [a / b for a, b in zip(times[2], times[4])]
        draws = sorted(
            statistics.median(ratios[rng.randrange(len(ratios))]
                              for _ in ratios)
            for _ in range(10000)
        )
        print(
            f"{curve} pairs={len(ratios)} "
            f"width2_median_ms={statistics.median(times[2]):.6f} "
            f"width4_median_ms={statistics.median(times[4]):.6f} "
            f"paired_ratio_median={statistics.median(ratios):.6f} "
            f"bootstrap95=[{draws[250]:.6f},{draws[9749]:.6f}] "
            f"width4_faster={sum(ratio > 1 for ratio in ratios)}"
        )


if __name__ == "__main__":
    main()
