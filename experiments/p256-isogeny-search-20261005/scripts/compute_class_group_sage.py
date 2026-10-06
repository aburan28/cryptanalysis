#!/usr/bin/env sage -python
"""Compute the P-256 CM class group with PARI's Buchmann-McCurley method."""

from __future__ import annotations

import argparse
import json
import math
import resource
import time
from pathlib import Path

try:
    from sage.all import pari
    from sage.env import SAGE_VERSION
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

D = -455213823400003756884736869668539463648899917731097708475249543966132856781915


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pari-stack-gib", type=int, default=4)
    parser.add_argument("--real-precision", type=int, default=128)
    parser.add_argument("--tech-c1", type=float)
    parser.add_argument("--tech-c2", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if (args.tech_c1 is None) != (args.tech_c2 is None):
        raise SystemExit("--tech-c1 and --tech-c2 must be supplied together")
    if args.tech_c1 is not None and not 0 <= args.tech_c1 <= args.tech_c2:
        raise SystemExit("require 0 <= tech-c1 <= tech-c2")

    pari.allocatemem(args.pari_stack_gib * 1024**3, silent=True)
    pari.default("realprecision", args.real_precision)
    configuration = {
        "discriminant": str(D),
        "method": "PARI quadclassunit (Buchmann-McCurley)",
        "correctness_basis": "provably correct under GRH using PARI's factor-base bound",
        "pari_stack_gib": args.pari_stack_gib,
        "real_precision": int(pari.default("realprecision")),
        "sage_version": str(SAGE_VERSION),
        "tech": (
            None
            if args.tech_c1 is None
            else [args.tech_c1, args.tech_c2]
        ),
    }
    print(json.dumps({"event": "start", **configuration}, sort_keys=True), flush=True)
    start = time.perf_counter()
    if args.tech_c1 is None:
        result = pari.quadclassunit(D)
    else:
        result = pari.quadclassunit(D, 0, [args.tech_c1, args.tech_c2])
    elapsed = time.perf_counter() - start

    class_number = int(result[0])
    cyclic_factors = [int(value) for value in result[1]]
    generators = [str(value) for value in result[2]]
    if math.prod(cyclic_factors) != class_number:
        raise AssertionError("cyclic factors do not multiply to the class number")
    payload = {
        "schema_version": 1,
        "configuration": configuration,
        "result": {
            "class_number": str(class_number),
            "class_number_bits": class_number.bit_length(),
            "cyclic_factors": [str(value) for value in cyclic_factors],
            "generators": generators,
            "regulator": str(result[3]),
        },
        "resources": {
            "elapsed_seconds": elapsed,
            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "event": "success",
                "class_number": str(class_number),
                "class_number_bits": class_number.bit_length(),
                "cyclic_factors": [str(value) for value in cyclic_factors],
                "elapsed_seconds": elapsed,
                "max_rss_kib": payload["resources"]["max_rss_kib"],
                "output": str(args.output),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
