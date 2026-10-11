"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import structural_report
from .registry import load_candidates
from .rho import benchmark_candidates, solve_toy_log


DEFAULT_CANDIDATES = Path("data/candidates/p256-root.json")
DEFAULT_TOY = Path("data/candidates/toy.json")


def _metadata() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_or_write(payload: dict[str, Any], output: str | None) -> None:
    payload = {"run": _metadata(), **payload}
    if output:
        path = Path(output)
        _write_json(path, payload)
        print(path)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _summary_markdown(
    structural: dict[str, Any], benchmark: dict[str, Any], toy: dict[str, Any]
) -> str:
    frobenius = structural["frobenius"]
    endomorphism = structural["endomorphism_orders"]
    row = benchmark["results"][0]
    return f"""# P-256 isogeny search run

## Structural result

- `D_pi = {frobenius['discriminant']['decimal']}`
- The stored complete factorization has {len(frobenius['absolute_discriminant_prime_factors'])} distinct prime factors.
- `D_pi` is fundamental: **{frobenius['discriminant_is_fundamental']}**.
- Frobenius-order conductor: **{endomorphism['frobenius_order_conductor_in_maximal_order']}**.
- There are no vertical volcano levels, exceptional `j`-invariants, or useful low-degree non-scalar endomorphisms in this isogeny class.

## Reference rho run

- Candidate: `{row['candidate_id']}`
- Iterations per second: `{row['iterations_per_second']:.2f}`
- Expected generic work: `2^{row['expected_generic_steps_log2']:.3f}` iterations before implementation-specific improvements.
- Toy collision recovered the discrete logarithm: **{toy['verified']}** in {toy['iterations']} iterations.

The timing is a reproducible Python control measurement, not a claim about the fastest available P-256 implementation. Candidate comparisons become meaningful when generated candidates are added with explicit isogeny paths and benchmarked through the same walk.
"""


def command_analyze(args: argparse.Namespace) -> None:
    report = structural_report(
        refactor=args.refactor, isogeny_prime_bound=args.prime_bound
    )
    _print_or_write(report, args.output)


def command_benchmark(args: argparse.Namespace) -> None:
    candidates = load_candidates(args.candidates)
    report = benchmark_candidates(
        candidates,
        seconds=args.seconds,
        table_size=args.table_size,
        batch_width=args.batch_width,
        trials=args.trials,
    )
    _print_or_write(report, args.output)


def command_toy(args: argparse.Namespace) -> None:
    candidate = load_candidates(args.candidate)[0]
    report = solve_toy_log(candidate, args.secret, seed=args.seed)
    _print_or_write(report, args.output)


def command_run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    structural = structural_report(isogeny_prime_bound=args.prime_bound)
    benchmark = benchmark_candidates(
        load_candidates(args.candidates),
        seconds=args.seconds,
        batch_width=args.batch_width,
        trials=args.trials,
    )
    toy = solve_toy_log(load_candidates(args.toy_candidate)[0], args.toy_secret)
    metadata = _metadata()
    _write_json(output_dir / "structural-report.json", {"run": metadata, **structural})
    _write_json(output_dir / "benchmark.json", {"run": metadata, **benchmark})
    _write_json(output_dir / "toy-rho.json", {"run": metadata, **toy})
    (output_dir / "summary.md").write_text(
        _summary_markdown(structural, benchmark, toy), encoding="utf-8"
    )
    print(output_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="p256-isogeny",
        description="P-256 isogeny-class structural search and ECDLP benchmarks",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="compute exact structural invariants")
    analyze.add_argument("--prime-bound", type=int, default=199)
    analyze.add_argument(
        "--refactor",
        action="store_true",
        help="rediscover D_pi's factorization instead of using the checked certificate",
    )
    analyze.add_argument("--output")
    analyze.set_defaults(func=command_analyze)

    benchmark = subparsers.add_parser("benchmark", help="benchmark rho walk iterations")
    benchmark.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    benchmark.add_argument("--seconds", type=float, default=1.0)
    benchmark.add_argument("--table-size", type=int, default=16)
    benchmark.add_argument("--batch-width", type=int, default=64)
    benchmark.add_argument("--trials", type=int, default=3)
    benchmark.add_argument("--output")
    benchmark.set_defaults(func=command_benchmark)

    toy = subparsers.add_parser("toy-rho", help="validate collision extraction on a toy curve")
    toy.add_argument("--candidate", type=Path, default=DEFAULT_TOY)
    toy.add_argument("--secret", type=int, default=4242)
    toy.add_argument("--seed", type=int, default=7)
    toy.add_argument("--output")
    toy.set_defaults(func=command_toy)

    run = subparsers.add_parser("run", help="run structural, timing, and toy experiments")
    run.add_argument("--output-dir", default="runs/latest")
    run.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    run.add_argument("--toy-candidate", type=Path, default=DEFAULT_TOY)
    run.add_argument("--toy-secret", type=int, default=4242)
    run.add_argument("--prime-bound", type=int, default=199)
    run.add_argument("--seconds", type=float, default=1.0)
    run.add_argument("--trials", type=int, default=3)
    run.add_argument("--batch-width", type=int, default=64)
    run.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
