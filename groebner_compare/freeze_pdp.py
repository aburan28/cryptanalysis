"""Freeze paired ECC2K17 point-decomposition fixtures before measurement.

Generated equations are versioned. Their generation time is outside solver
stage totals. Seeds are public planted correctness controls, not estimates of
ordinary unplanted relation yield or full DLP runtime.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .runner import validate


def freeze(seeds=(1, 2, 3), *, include_hybrid_sat=False):
    source = Path(__file__).resolve().parents[1] / "experiments/pdp-scaling"
    sys.path.insert(0, str(source))
    from descend import make_instance, verify_solution
    instances = []
    for seed in seeds:
        inst = make_instance(17, 3, 3, seed, b=1)
        assert verify_solution(inst, inst.planted)
        instances.append({"id": f"ecc2k17-s3-l3-seed-{seed}",
                          "equations": [sorted(eq) for eq in inst.equations()],
                          "blocks": [3, 3, 3], "hybrid_guess": 3,
                          "pdp": {"n": inst.n, "m": inst.m, "l": inst.l,
                                  "seed": seed, "b": inst.b, "mod": inst.mod,
                                  "xR": inst.xR, "planted": inst.planted}})
    def backend(name, command, provenance):
        return {"id": name, "mode": "warm", "command": command,
                "provenance": provenance}
    names = ("cryptominisat", "xor-sat", "repository-f5b", "block-f4",
             "elimlin-f4", "hybrid-f4")
    if include_hybrid_sat:
        names += ("hybrid-cryptominisat",)
    names += ("m5gb",)
    backends = [backend(name, (["python", "-m", "groebner_compare.worker", name]
                                if name == "repository-f5b" else
                                ["python", "-m", "groebner_compare.research_worker", name]),
                        ("manschga/M5GB upstream commit 2d063f748e8a16ac5a1d74641c79725df29f67ac; binary sha256 in response; set M5GB_BINARY"
                         if name == "m5gb" else
                         "local wrapper SHA in host.json; solver version in response where external"))
                for name in names]
    manifest = {"schema": 1, "encoding": "ecc2k17-s3-l3-planted-weil-descent-v1",
                "ring": {"field": "GF(2)", "quotient": "x_i^2+x_i",
                         "order": "degrevlex", "nvars": 9,
                         "variables": [f"x{i}" for i in range(9)]},
                "watchdog_seconds": 5, "threads": 1,
                "instances": instances, "backends": backends,
                "witness_verifier": {"command": ["python", "-m",
                                                  "groebner_compare.pdp_verifier"],
                                     "provenance": "independent original ANF and ECC point-sum replay; source SHA in host.json"}}
    return validate(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--include-hybrid-sat", action="store_true")
    args = parser.parse_args()
    args.output.write_text(json.dumps(freeze(include_hybrid_sat=args.include_hybrid_sat),
                                    sort_keys=True, indent=2) + "\n")
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
