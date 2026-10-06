"""Build and run the compiled Boolean signature engine with Python verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from boolean_f5b import BooleanF5B
from boolean_basis import basis_vanishes
from descend import verify_solution


SOURCE = Path(__file__).with_name("boolean_f5b_native.cpp")


def native_binary() -> tuple[Path, dict]:
    source = SOURCE.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    binary = Path(tempfile.gettempdir()) / f"boolean-f5b-native-{digest[:16]}"
    built = False
    build_seconds = 0.0
    if not binary.exists():
        started = time.monotonic()
        temporary = binary.with_name(binary.name + f".{os.getpid()}.tmp")
        subprocess.run(
            ["g++", "-O3", "-std=c++17", str(SOURCE), "-o", str(temporary)],
            check=True, capture_output=True, text=True, timeout=60)
        os.replace(temporary, binary)
        build_seconds = time.monotonic() - started
        built = True
    return binary, {
        "source_sha256": digest,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "compiled_this_run": built,
        "build_seconds": build_seconds,
    }


def solve_native(instance, timeout: float, signature_limit: int,
                 completion_seed_limit: int | None = None) -> dict:
    if instance.nvars > 12:
        return {"status": "unsupported", "complete": False,
                "detail": "compiled Boolean F5B currently supports at most 12 variables"}
    equations = [sorted(equation) for equation in instance.equations() if equation]
    if completion_seed_limit is None:
        completion_seed_limit = -1
    data = (f"{instance.nvars} {len(equations)} {signature_limit} "
            f"{completion_seed_limit}\n") + "".join(
        f"{len(equation)} {' '.join(map(str, equation))}\n"
        for equation in equations)
    binary, build = native_binary()
    started = time.monotonic()
    try:
        process = subprocess.run(
            [str(binary)], input=data, text=True, capture_output=True,
            timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "complete": False,
                "wall_seconds": time.monotonic() - started,
                "native_build": build}
    wall = time.monotonic() - started
    if process.returncode != 0:
        return {"status": "error", "complete": False,
                "returncode": process.returncode,
                "stderr": process.stderr[-1000:], "native_build": build}
    lines = process.stdout.splitlines()
    head = lines[0].split() if lines else []
    if len(head) != 10 or head[0] != "OK":
        return {"status": "error", "complete": False,
                "detail": "invalid native output", "stdout": process.stdout[-1000:],
                "native_build": build}
    basis_size = int(head[1])
    if len(lines) != basis_size + 1:
        return {"status": "error", "complete": False,
                "detail": "native basis length mismatch", "native_build": build}
    basis_terms = []
    for line in lines[1:]:
        fields = list(map(int, line.split()))
        if not fields or fields[0] != len(fields) - 1:
            return {"status": "error", "complete": False,
                    "detail": "invalid native basis row", "native_build": build}
        basis_terms.append(fields[1:])
    verifier = BooleanF5B(instance.nvars, timeout=max(5, timeout))
    basis = [verifier.from_terms(terms) for terms in basis_terms]
    generators = [verifier.from_terms(equation) for equation in equations]
    reduction_rows = verifier.reduction_table(basis)
    groebner = verifier.is_groebner(basis, reduction_rows)
    generators_ok = all(verifier.normal_form(generator, basis, reduction_rows) == 0
                        for generator in generators)
    basis_hash = hashlib.sha256(json.dumps(
        [sorted(terms) for terms in basis_terms], sort_keys=True).encode()).hexdigest()
    result = {
        "status": "gb", "complete": instance.nvars <= 20,
        "basis_size": basis_size, "basis_seconds": float(head[2]),
        "signature_insertions": int(head[3]), "reductions": int(head[4]),
        "completion_seed_limit": completion_seed_limit,
        "phase_seconds": {
            "initial": float(head[5]), "signature": float(head[6]),
            "interreduce": float(head[7]), "completion": float(head[8]),
            "final_reduce": float(head[9]),
        },
        "basis_sha256": basis_hash,
        "groebner_verified": groebner,
        "generators_reduce_to_zero": generators_ok,
        "wall_seconds": wall,
        "native_build": build,
    }
    if not groebner or not generators_ok:
        result["status"] = "verification-failed"
        result["complete"] = False
        return result
    checked = 0
    candidates = 0
    extraction_started = time.monotonic()
    for assignment in range(1 << instance.nvars):
        checked += 1
        if not basis_vanishes(basis_terms, assignment):
            continue
        candidates += 1
        if instance.evaluate(assignment) == 0 and verify_solution(instance, assignment):
            result.update({"status": "solved", "assignment": assignment,
                           "verified": True,
                           "is_planted": sorted(instance.x_from_assignment(assignment)) ==
                               sorted(instance.x_from_assignment(instance.planted))})
            break
    result["assignments_checked"] = checked
    result["basis_candidates_checked"] = candidates
    result["extraction_seconds"] = time.monotonic() - extraction_started
    if result["status"] == "gb":
        result["status"] = "gb-no-verified-solution"
    return result
