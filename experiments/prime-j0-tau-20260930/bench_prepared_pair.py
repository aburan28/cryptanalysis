"""Run alternating, verified one-target rho pairs on frozen j0 workloads."""

import argparse
import pathlib
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width2", type=pathlib.Path, required=True)
    parser.add_argument("--width4", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--curves", nargs="+", default=("glv-j0-26", "glv-j0-32"))
    parser.add_argument("--scalar", help="fixture scalar for bench binaries that accept it")
    parser.add_argument("--walk-seed", help="walk seed for bench binaries that accept it")
    parser.add_argument("--pairs", type=int, default=12)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    for curve in args.curves:
        rows = {2: [], 4: []}
        for pair in range(args.pairs):
            order = (2, 4) if pair % 2 == 0 else (4, 2)
            for width in order:
                binary = args.width2 if width == 2 else args.width4
                command = [str(binary.resolve()), curve, "1"]
                if args.scalar is not None:
                    command.append(args.scalar)
                    if args.walk_seed is not None:
                        command.append(args.walk_seed)
                elif args.walk_seed is not None:
                    parser.error("--walk-seed requires --scalar")
                proc = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result = proc.stdout.strip()
                if "verified=1" not in result or result.count("\n"):
                    raise RuntimeError(f"unexpected result: {result!r}")
                rows[width].append(f"pair={pair + 1} width={width} {result}\n")
        for width in (2, 4):
            path = args.output / f"rho_{curve}_width{width}_prepared_pair.txt"
            path.write_text("".join(rows[width]))
            print(path)


if __name__ == "__main__":
    main()
