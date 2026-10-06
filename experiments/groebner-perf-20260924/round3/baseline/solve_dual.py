"""Opt-in, bounded PDP experiment using exact evaluation and interpolation.

No F4/F5 dispatch default changes. This is a Boolean solver research control,
not a new-algorithm or complete-DLP claim. Build with round2/build.py first.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "pdp-scaling"))
from boolean_basis import basis_vanishes, canonical_terms, certify_boolean_basis
from descend import make_instance, verify_solution

_LIBRARY = None


class DualStats(ctypes.Structure):
    _fields_ = [("roots", ctypes.c_uint32), ("rows", ctypes.c_uint32),
                ("standard", ctypes.c_uint32), ("frontier", ctypes.c_uint32),
                ("evaluation", ctypes.c_double), ("interpolation", ctypes.c_double)]


def _in_process(nvars, equations):
    global _LIBRARY
    library = HERE / "build" / ("boolean-dual.dylib" if sys.platform == "darwin" else "boolean-dual.so")
    if _LIBRARY is None:
        lib = ctypes.CDLL(str(library))
        pointer = ctypes.POINTER(ctypes.c_uint32)
        lib.dual_compute.argtypes = [ctypes.c_uint32, pointer, ctypes.c_uint32, pointer,
                                    ctypes.c_uint32, ctypes.POINTER(DualStats)]
        lib.dual_compute.restype = ctypes.c_void_p
        lib.dual_error.restype = ctypes.c_char_p
        lib.dual_row_size.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.dual_row_size.restype = ctypes.c_uint32
        lib.dual_row_data.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.dual_row_data.restype = pointer
        lib.dual_destroy.argtypes = [ctypes.c_void_p]
        lib.dual_destroy.restype = None
        _LIBRARY = lib
    flat = []
    offsets = [0]
    for g in equations:
        flat.extend(g)
        offsets.append(len(flat))
    data = (ctypes.c_uint32 * len(flat))(*flat)
    starts = (ctypes.c_uint32 * len(offsets))(*offsets)
    stats = DualStats()
    handle = _LIBRARY.dual_compute(nvars, data, len(flat), starts, len(equations), ctypes.byref(stats))
    if not handle:
        return None, {"error": _LIBRARY.dual_error().decode()}, library
    try:
        basis = [list(_LIBRARY.dual_row_data(handle, i)[:_LIBRARY.dual_row_size(handle, i)])
                 for i in range(stats.rows)]
    finally:
        _LIBRARY.dual_destroy(handle)
    metrics = {"roots": stats.roots, "evaluation_seconds": stats.evaluation,
               "interpolation_seconds": stats.interpolation,
               "standard_monomials": stats.standard, "frontier_visits": stats.frontier}
    return basis, metrics, library


def compute_dual_basis(nvars, equations, timeout=30, binary=None, transport="library"):
    if not 1 <= nvars <= 20:
        return {"status": "unsupported", "complete": False,
                "detail": "this wrapper's independent certificate is bounded to 20 variables"}
    binary = Path(binary or HERE / "build/boolean-dual")
    equations = [canonical_terms(g) for g in equations]
    if any(not 0 <= m < 1 << nvars for g in equations for m in g):
        raise ValueError("monomial outside the Boolean ring")
    start = time.perf_counter()
    if transport == "library":
        basis, metrics, binary = _in_process(nvars, equations)
        wall = time.perf_counter() - start
        if basis is None:
            return {"status": "inconclusive", "complete": False, "wall_seconds": wall,
                    "detail": metrics["error"]}
        basis_seconds = metrics["evaluation_seconds"] + metrics["interpolation_seconds"]
    elif transport == "subprocess":
        data = f"{nvars} {len(equations)} 0 0\n" + "".join(
            f'{len(g)} {" ".join(map(str, g))}\n' for g in equations)
        try:
            process = subprocess.run([str(binary.resolve())], input=data, text=True,
                                     capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "complete": False,
                    "wall_seconds": time.perf_counter() - start}
        wall = time.perf_counter() - start
        if process.returncode:
            return {"status": "inconclusive", "complete": False, "wall_seconds": wall,
                    "returncode": process.returncode, "detail": process.stderr[-1000:]}
        lines = process.stdout.splitlines()
        head = lines[0].split() if lines else []
        if len(head) != 14 or head[0] != "OK" or len(lines) != int(head[1]) + 1:
            raise RuntimeError("invalid dual-solver output")
        basis = []
        for line in lines[1:]:
            row = list(map(int, line.split()))
            if not row or row[0] != len(row) - 1:
                raise RuntimeError("invalid dual-solver row")
            basis.append(row[1:])
        basis_seconds = float(head[2])
        metrics = json.loads(process.stderr)
    else:
        raise ValueError("transport must be library or subprocess")
    start = time.perf_counter()
    certificate = certify_boolean_basis(nvars, equations, basis, monomial_cache=nvars <= 12)
    verification = time.perf_counter() - start
    return {"status": "gb" if certificate["verified"] else "verification-failed",
            "complete": certificate["verified"], "basis_terms": basis,
            "basis_sha256": hashlib.sha256(json.dumps([sorted(g) for g in basis], sort_keys=True).encode()).hexdigest(),
            "basis_seconds": basis_seconds, "wall_seconds": wall, "transport": transport,
            "hard_subprocess_timeout": transport == "subprocess",
            "verification_seconds": verification, "basis_certificate": certificate,
            "groebner_verified": certificate["verified"],
            "generators_reduce_to_zero": certificate["verified"],
            "algorithm": "exact-evaluation+buchberger-moller",
            "metrics": metrics,
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}


def solve_dual(instance, timeout=30, binary=None, transport="library"):
    result = compute_dual_basis(instance.nvars, instance.equations(), timeout, binary, transport)
    if result["status"] != "gb":
        result.pop("basis_terms", None)
        return result
    basis = result.pop("basis_terms")
    start = time.perf_counter()
    checked = candidates = 0
    solutions = result["basis_certificate"].get("solutions")
    assignments = range(1 << instance.nvars) if solutions is None else solutions
    result["assignment_search"] = "basis-filtered-enumeration" if solutions is None else "certified-input-roots"
    for assignment in assignments:
        checked += 1
        if solutions is None and not basis_vanishes(basis, assignment):
            continue
        candidates += 1
        if instance.evaluate(assignment) == 0 and verify_solution(instance, assignment):
            result.update(status="solved", verified=True, assignment=assignment)
            break
    if result["status"] == "gb":
        result["status"] = "gb-no-verified-solution"
    result.update(assignments_checked=checked, basis_candidates_checked=candidates,
                  extraction_seconds=time.perf_counter() - start)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=31)
    parser.add_argument("--m", type=int, default=3)
    parser.add_argument("--ell", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--transport", choices=["library", "subprocess"], default="library")
    args = parser.parse_args()
    start = time.perf_counter()
    instance = make_instance(args.n, args.m, args.ell, seed=args.seed)
    setup = time.perf_counter() - start
    start = time.perf_counter()
    result = solve_dual(instance, transport=args.transport)
    result.update(query_seconds=time.perf_counter() - start, instance_setup_seconds=setup,
                  scope="PDP stage diagnostic; no relation collection/final LA/complete DLP cost")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
