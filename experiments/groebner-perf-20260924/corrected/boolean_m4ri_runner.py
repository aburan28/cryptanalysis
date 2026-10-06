"""Build and verify the bounded F5-signature plus M4RI completion backend."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from boolean_f5b import BooleanF5B
from descend import verify_solution


SOURCE = Path(__file__).with_name("boolean_f5b_m4ri.cpp")
NATIVE_SOURCE = Path(__file__).with_name("boolean_f5b_native.cpp")


def _m4ri_prefix() -> Path:
    candidates = []
    configured = os.environ.get("M4RI_PREFIX")
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path("/var/tmp/sage-10.9-current/local"))
    for prefix in candidates:
        if ((prefix / "include/m4ri/m4ri.h").is_file() and
                any((prefix / "lib").glob("libm4ri.*"))):
            return prefix
    raise RuntimeError(
        "M4RI was not found; set M4RI_PREFIX to a prefix containing "
        "include/m4ri/m4ri.h and lib/libm4ri")


def m4ri_binary() -> tuple[Path, dict]:
    prefix = _m4ri_prefix()
    libraries = sorted((prefix / "lib").glob("libm4ri.*"))
    library = next((path for path in libraries if path.is_file()), None)
    if library is None:
        raise RuntimeError("M4RI library is missing")
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    native_hash = hashlib.sha256(NATIVE_SOURCE.read_bytes()).hexdigest()
    library_hash = hashlib.sha256(library.read_bytes()).hexdigest()
    compile_args = [
        "g++", "-O3", "-std=c++17", f"-I{prefix / 'include'}",
        str(SOURCE), f"-L{prefix / 'lib'}", "-lm4ri",
        f"-Wl,-rpath,{prefix / 'lib'}",
    ]
    if sys.platform == "darwin":
        compile_args.append("-Wl,-no_uuid")
    recipe = "stable-output-name-v1\0" + "\0".join(compile_args)
    identity = hashlib.sha256(
        (source_hash + native_hash + library_hash + str(prefix) + recipe).encode()
    ).hexdigest()
    binary = Path(tempfile.gettempdir()) / f"boolean-f5b-m4ri-{identity[:16]}"
    built = False
    build_seconds = 0.0
    if not binary.exists():
        started = time.monotonic()
        environment = os.environ.copy()
        environment.setdefault("TMPDIR", tempfile.gettempdir())
        # Mach-O's ad-hoc signature embeds the output basename. Compile under
        # the final basename in a private directory so concurrent builds are
        # byte-identical, then atomically publish the result.
        with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as build_dir:
            temporary = Path(build_dir) / binary.name
            subprocess.run(
                compile_args + ["-o", str(temporary)],
                check=True, capture_output=True, text=True, timeout=90,
                env=environment)
            os.replace(temporary, binary)
        build_seconds = time.monotonic() - started
        built = True
    return binary, {
        "source_sha256": source_hash,
        "native_source_sha256": native_hash,
        "m4ri_library": str(library),
        "m4ri_library_sha256": library_hash,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "compile_recipe_sha256": hashlib.sha256(recipe.encode()).hexdigest(),
        "compiled_this_run": built,
        "build_seconds": build_seconds,
    }


def compute_m4ri_basis(nvars: int, equations, timeout: float,
                       signature_limit: int, matrix_degree: int = 8,
                       verify: bool = True) -> dict:
    """Compute and independently verify a complete basis for raw ANF rows."""
    if nvars < 1 or nvars > 12:
        return {"status": "unsupported", "complete": False,
                "detail": "M4RI completion supports between 1 and 12 variables"}
    if signature_limit < 0:
        raise ValueError("signature_limit must be nonnegative")
    matrix_degree = min(matrix_degree, nvars)
    if matrix_degree < 0:
        raise ValueError("matrix_degree must be nonnegative")
    equations = [sorted(set(equation)) for equation in equations if equation]
    if any(monomial < 0 or monomial >= 1 << nvars
           for equation in equations for monomial in equation):
        raise ValueError("equation contains a monomial outside the Boolean ring")
    data = (f"{nvars} {len(equations)} {signature_limit} "
            f"{matrix_degree}\n") + "".join(
        f"{len(equation)} {' '.join(map(str, equation))}\n"
        for equation in equations)
    try:
        binary, build = m4ri_binary()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        return {"status": "unavailable", "complete": False,
                "detail": str(error)}
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
    if len(head) != 14 or head[0] != "OK":
        return {"status": "error", "complete": False,
                "detail": "invalid M4RI output", "stdout": process.stdout[-1000:],
                "stderr": process.stderr[-1000:], "native_build": build}
    basis_size = int(head[1])
    if len(lines) != basis_size + 1:
        return {"status": "error", "complete": False,
                "detail": "M4RI basis length mismatch", "native_build": build}
    basis_terms = []
    for line in lines[1:]:
        fields = list(map(int, line.split()))
        if not fields or fields[0] != len(fields) - 1:
            return {"status": "error", "complete": False,
                    "detail": "invalid M4RI basis row", "native_build": build}
        basis_terms.append(fields[1:])

    groebner = None
    generators_ok = None
    if verify:
        verifier = BooleanF5B(nvars, timeout=max(5, timeout))
        basis = [verifier.from_terms(terms) for terms in basis_terms]
        generators = [verifier.from_terms(equation) for equation in equations]
        groebner = verifier.is_groebner(basis)
        generators_ok = all(verifier.normal_form(generator, basis) == 0
                            for generator in generators)
    basis_hash = hashlib.sha256(json.dumps(
        [sorted(terms) for terms in basis_terms], sort_keys=True).encode()).hexdigest()
    result = {
        "status": "gb", "complete": True,
        "algorithm": "bounded-f5-signatures+m4ri-boolean-macaulay+certified-completion",
        "basis_size": basis_size,
        "basis_seconds": float(head[2]),
        "signature_insertions": int(head[3]),
        "signature_pairs_processed": int(head[4]),
        "signature_seconds": float(head[5]),
        "matrix_degree": matrix_degree,
        "matrix_rows": int(head[6]),
        "matrix_rank": int(head[7]),
        "matrix_seconds": {
            "generation": float(head[8]),
            "population": float(head[9]),
            "elimination": float(head[10]),
            "extraction_and_completion": float(head[11]),
        },
        "f5_rows_admitted": int(head[12]),
        "f5_remainders_admitted": int(head[13]),
        "basis_sha256": basis_hash,
        "groebner_verified": groebner,
        "generators_reduce_to_zero": generators_ok,
        "independent_basis_verification": verify,
        "wall_seconds": wall,
        "native_build": build,
        "basis_terms": basis_terms,
    }
    if verify and (not groebner or not generators_ok):
        result["status"] = "verification-failed"
        result["complete"] = False
        return result
    return result


def solve_m4ri(instance, timeout: float, signature_limit: int,
               matrix_degree: int = 8) -> dict:
    """Run the hybrid and independently verify the basis and curve witness."""
    equations = [sorted(equation) for equation in instance.equations() if equation]
    result = compute_m4ri_basis(instance.nvars, equations, timeout,
                                signature_limit, matrix_degree)
    if result["status"] != "gb":
        result.pop("basis_terms", None)
        return result
    result.pop("basis_terms", None)
    checked = 0
    extraction_started = time.monotonic()
    for assignment in range(1 << instance.nvars):
        checked += 1
        if instance.evaluate(assignment) == 0 and verify_solution(instance, assignment):
            result.update({
                "status": "solved", "assignment": assignment, "verified": True,
                "is_planted": sorted(instance.x_from_assignment(assignment)) ==
                    sorted(instance.x_from_assignment(instance.planted)),
            })
            break
    result["assignments_checked"] = checked
    result["extraction_seconds"] = time.monotonic() - extraction_started
    if result["status"] == "gb":
        result["status"] = "gb-no-verified-solution"
    return result
