"""Independently regenerate and check real small-ECC PDP witnesses.

This runs outside the candidate solver and also checks the curve group law:
Boolean roots alone need not lift to a valid point decomposition.
"""

import contextlib
import json
from pathlib import Path
import sys

from .certificate import terms


def check(request):
    spec = request["instance"]["pdp"]
    source = Path(__file__).resolve().parents[1] / "experiments/pdp-scaling"
    sys.path.insert(0, str(source))
    from descend import make_instance, verify_solution

    inst = make_instance(spec["n"], spec["m"], spec["l"], spec["seed"], spec["b"])
    if ({"n": inst.n, "m": inst.m, "l": inst.l, "seed": spec["seed"],
         "b": inst.b, "mod": inst.mod, "xR": inst.xR, "planted": inst.planted}
            != spec or request["ring"]["nvars"] != inst.nvars
            or terms(request["instance"]["equations"], inst.nvars)
            != terms([sorted(row) for row in inst.equations()], inst.nvars)):
        raise ValueError("frozen point decomposition does not match independent regeneration")
    candidates = request["solutions"]
    if (not isinstance(candidates, list) or any(type(v) is not int or v < 0
            or v >= 1 << inst.nvars for v in candidates)):
        raise ValueError("invalid assignment masks")
    return {"status": "ok", "verified_solutions": [v for v in candidates
                                                     if verify_solution(inst, v)]}


def main():
    for line in sys.stdin:
        request = json.loads(line)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                reply = check(request) if request["operation"] == "verify_witnesses" else {
                    "status": "incompatible", "reason": "verification only"}
        except (ImportError, KeyError, TypeError, ValueError) as error:
            reply = {"status": "error", "reason": str(error)}
        reply["request_id"] = request["request_id"]
        print(json.dumps(reply, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
