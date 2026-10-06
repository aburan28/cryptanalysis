"""Explicit native transport for the independent Boolean dimension certificate.

Build with ../groebner-perf-20260924/round3/build.py. There is no automatic
compiler invocation or fallback that could silently change benchmark arms.
"""
import ctypes
from pathlib import Path
import sys

DEFAULT_LIBRARY = Path(__file__).resolve().parent.parent / "groebner-perf-20260924/round3/build" / (
    "boolean-certificate.dylib" if sys.platform == "darwin" else "boolean-certificate.so")
_LIBRARIES = {}


class Certificate(ctypes.Structure):
    _fields_ = [("code", ctypes.c_uint32), ("roots", ctypes.c_uint32),
                ("standard", ctypes.c_uint32), ("solution_count", ctypes.c_uint32),
                ("solutions", ctypes.c_uint32*256), ("scatter_words", ctypes.c_uint64),
                ("scalar_terms", ctypes.c_uint64)]


def _pack(rows, nvars):
    flat, offsets = [], [0]
    for row in rows:
        for mask in row:
            if not isinstance(mask, int) or not 0 <= mask < (1 << nvars):
                raise ValueError("monomial outside the Boolean ring")
            flat.append(mask)
        offsets.append(len(flat))
    if len(flat) >= 1 << 32 or len(offsets) >= 1 << 32:
        raise ValueError("certificate input exceeds uint32 ABI")
    return ((ctypes.c_uint32*len(flat))(*flat),
            (ctypes.c_uint32*len(offsets))(*offsets))


def load_library(path=DEFAULT_LIBRARY):
    path = str(Path(path).resolve())
    if path not in _LIBRARIES:
        lib = ctypes.CDLL(path)
        pointer = ctypes.POINTER(ctypes.c_uint32)
        lib.boolean_certificate.argtypes = [ctypes.c_uint32, pointer, ctypes.c_uint32,
            pointer, ctypes.c_uint32, pointer, ctypes.c_uint32, pointer,
            ctypes.c_uint32, ctypes.POINTER(Certificate)]
        lib.boolean_certificate.restype = ctypes.c_int
        _LIBRARIES[path] = lib
    return _LIBRARIES[path]


def certify_boolean_basis_native(nvars, equations, basis_terms, *, library=DEFAULT_LIBRARY):
    if not isinstance(nvars, int) or not 1 <= nvars <= 20:
        raise ValueError("native certificate variable bound: 1..20")
    data, starts = _pack(equations, nvars)
    basis, offsets = _pack(basis_terms, nvars)
    result = Certificate()
    code = load_library(library).boolean_certificate(nvars, data, len(data), starts,
        len(starts)-1, basis, len(basis), offsets, len(offsets)-1, ctypes.byref(result))
    if code == 6:
        raise ValueError("invalid native certificate input")
    if code == 7:
        raise RuntimeError("native certificate allocation or internal failure")
    answer = {"verified": code == 0, "method": "exact-Boolean-zeros-and-staircase",
              "backend": "native-direct-anf", "root_count": result.roots,
              "standard_monomials": result.standard,
              "evaluation_counts": {"scatter_words": result.scatter_words,
                                    "scalar_terms": result.scalar_terms}}
    if code:
        answer["reason"] = {1: "noncanonical or zero basis row", 2: "basis removes an input root",
            3: "staircase dimension differs from root count", 4: "nonminimal leading monomial",
            5: "nonstandard tail monomial"}[code]
    else:
        answer.update(ideal_equality=True, reduced_groebner_basis=True,
            solutions=list(result.solutions[:result.solution_count]) if result.roots <= 256 else None)
    return answer
