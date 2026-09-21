"""Python bindings for libcryptanalysis, a discrete-logarithm cryptanalysis toolkit.

Quick start::

    import cryptanalysis as ca

    G = ca.Group.zp(2000000579, order=1000000289)
    g = G.find_generator(seed=1)
    h = G.mul(g, 123456789)
    x, stats = G.dlog(g, h)  # Pohlig-Hellman + auto solver
    assert x == 123456789

All integers cross the FFI as 64-bit unsigned values: moduli, orders,
exponents and coordinates must lie in ``[0, 2**64)``.
"""

from __future__ import annotations

from . import _lib
from ._lib import ENV_VAR, library_path, status_string
from ._types import (
    Elem,
    ElemLike,
    GroupKind,
    ICMethod,
    ICParams,
    ICStats,
    Options,
    Solver,
    Stats,
)
from .curve import CurveEndo, CurveInfo, curve_by_name, curve_detect, curve_names
from .errors import (
    CryptanalysisError,
    InternalError,
    InvalidError,
    LimitError,
    NoMemoryError,
    NotFoundError,
    SingularError,
    Status,
    UnsupportedError,
)
from .group import Group, cheon_best_divisor
from .indexcalc import ICContext, ic_auto_params, ic_solve
from .ntheory import factorize, invmod, is_prime, next_prime, powmod, primitive_root

__version__ = "0.1.0"


def version() -> str:
    """The version string reported by the loaded C library (``ca_version()``)."""
    return _lib.lib.ca_version().decode("ascii")


__all__ = [
    "ENV_VAR",
    "CryptanalysisError",
    "CurveEndo",
    "CurveInfo",
    "Elem",
    "ElemLike",
    "Group",
    "GroupKind",
    "ICContext",
    "ICMethod",
    "ICParams",
    "ICStats",
    "InternalError",
    "InvalidError",
    "LimitError",
    "NoMemoryError",
    "NotFoundError",
    "Options",
    "SingularError",
    "Solver",
    "Stats",
    "Status",
    "UnsupportedError",
    "__version__",
    "cheon_best_divisor",
    "curve_by_name",
    "curve_detect",
    "curve_names",
    "factorize",
    "ic_auto_params",
    "ic_solve",
    "invmod",
    "is_prime",
    "library_path",
    "next_prime",
    "powmod",
    "primitive_root",
    "status_string",
    "version",
]
