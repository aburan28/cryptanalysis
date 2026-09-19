"""Public value types: group elements, enums and the option/statistics records."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import NamedTuple, Sequence, Union

from . import _lib
from ._lib import CICParams, CICStats, COptions, CStats, Words


class GroupKind(IntEnum):
    """``ca_ctx_kind()`` values."""

    ZP = 1  # multiplicative group Z_p^*
    EC = 2  # elliptic curve E(F_p)


class Solver(IntEnum):
    """``ca_solver``: which algorithm ``Group.dlog`` uses for each prime-power factor."""

    AUTO = 0
    BSGS = 1
    RHO = 2
    KANGAROO = 3
    GRUMPY = 4
    BRUTE = 5


class ICMethod(IntEnum):
    """``ca_ic_method``: index-calculus relation collector."""

    LINEAR_SIEVE = 0
    RANDOM_EXPONENT = 1


# --------------------------------------------------------------------------
# Elements
# --------------------------------------------------------------------------


class Elem(NamedTuple):
    """A group element in the public word form of ``ca_ffi.h``.

    * Z_p^*  : ``x`` is the residue in ``[1, p)``; ``y`` and ``inf`` are unused.
    * E(F_p) : affine coordinates ``(x, y)``, or ``inf=True`` for the point at
      infinity (``x`` and ``y`` are then ignored).

    Wherever the API takes an element you may also pass a plain ``int`` for a
    Z_p^* element, or a 2-, 3- or 4-tuple of ints (``(x, y[, inf[, 0]])``).
    """

    x: int
    y: int = 0
    inf: bool = False

    @classmethod
    def from_words(cls, words: Sequence[int]) -> "Elem":
        """Build an element from ``uint64_t[4]`` words."""
        return cls(int(words[0]), int(words[1]), bool(words[2]))

    def words(self) -> tuple[int, int, int, int]:
        """The ``uint64_t[4]`` representation used by the C ABI."""
        return (self.x, self.y, 1 if self.inf else 0, 0)

    def __int__(self) -> int:
        """The residue of a Z_p^* element (``x``)."""
        return self.x

    def __repr__(self) -> str:
        if self.inf:
            return "Elem(inf=True)"
        if self.y == 0:
            return f"Elem(x={self.x})"
        return f"Elem(x={self.x}, y={self.y})"


ElemLike = Union[Elem, int, Sequence[int]]


def to_words(value: ElemLike, kind: GroupKind, name: str = "element") -> Words:
    """Convert any accepted element representation to a ctypes ``uint64_t[4]``."""
    if isinstance(value, Elem):
        w = value.words()
    elif isinstance(value, bool):
        raise TypeError(f"{name}: bool is not a group element")
    elif isinstance(value, int):
        if kind == GroupKind.EC:
            raise TypeError(
                f"{name}: a plain int is only accepted for Z_p^* elements; "
                "use Elem(x, y) or (x, y) for a curve point"
            )
        w = (value, 0, 0, 0)
    elif isinstance(value, (tuple, list)) and 1 <= len(value) <= 4:
        if kind == GroupKind.EC and len(value) == 1:
            raise TypeError(f"{name}: a curve point needs (x, y) or Elem(inf=True)")
        vals = [int(v) if isinstance(v, bool) else v for v in value]
        w = tuple(vals) + (0,) * (4 - len(vals))
    else:
        raise TypeError(
            f"{name} must be an Elem, an int (Z_p^* only) or a tuple of up to 4 ints, "
            f"not {type(value).__name__}"
        )
    return Words(*(_lib.u64(v, f"{name}[{i}]") for i, v in enumerate(w)))


def from_words(w: Words) -> Elem:
    return Elem(int(w[0]), int(w[1]), bool(w[2]))


# --------------------------------------------------------------------------
# Solver options / statistics
# --------------------------------------------------------------------------


@dataclass
class Options:
    """Solver options mirroring ``ca_ffi_options`` (defaults = ``ca_ffi_options_default``).

    A value of 0 (or -1 for the ``*_dp_bits`` fields) means "let the library choose".
    """

    threads: int = 1  # rho worker threads (0 => 1)
    seed: int = 0  # 0 => random
    max_ops: int = 0  # 0 => unlimited (raises LimitError when exceeded)
    bsgs_table_size: int = 0  # 0 => sqrt(width)
    rho_r: int = 0  # 0 => auto
    rho_dp_bits: int = -1  # -1 => auto
    rho_walks_per_thread: int = 0
    rho_negation_map: bool = True  # use the negation map when available
    rho_max_table_entries: int = 0
    kangaroo_herd_size: int = 0  # 0 => auto
    kangaroo_dp_bits: int = -1  # -1 => auto
    kangaroo_jumps: int = 0  # 0 => auto
    grumpy_m: int = 0  # 0 => alpha*sqrt(width)
    grumpy_alpha: float = 0.7  # 0 => 0.7
    solver: Solver = Solver.AUTO  # dlog driver
    bsgs_max_prime: int = 0  # auto: BSGS for prime factors <= this (0 => 2^36)

    @classmethod
    def library_defaults(cls) -> "Options":
        """The defaults as reported by the C library (``ca_ffi_options_default``)."""
        c = COptions()
        _lib.lib.ca_ffi_options_default(ctypes.byref(c))
        return cls.from_c(c)

    @classmethod
    def from_c(cls, c: COptions) -> "Options":
        return cls(
            threads=c.threads,
            seed=c.seed,
            max_ops=c.max_ops,
            bsgs_table_size=c.bsgs_table_size,
            rho_r=c.rho_r,
            rho_dp_bits=c.rho_dp_bits,
            rho_walks_per_thread=c.rho_walks_per_thread,
            rho_negation_map=bool(c.rho_negation_map),
            rho_max_table_entries=c.rho_max_table_entries,
            kangaroo_herd_size=c.kangaroo_herd_size,
            kangaroo_dp_bits=c.kangaroo_dp_bits,
            kangaroo_jumps=c.kangaroo_jumps,
            grumpy_m=c.grumpy_m,
            grumpy_alpha=c.grumpy_alpha,
            solver=Solver(c.solver),
            bsgs_max_prime=c.bsgs_max_prime,
        )

    def to_c(self) -> COptions:
        """Convert to the C struct (starting from the library defaults so that
        reserved fields keep whatever the library expects)."""
        c = COptions()
        _lib.lib.ca_ffi_options_default(ctypes.byref(c))
        c.threads = _lib.u32(self.threads, "threads")
        c.seed = _lib.u64(self.seed, "seed")
        c.max_ops = _lib.u64(self.max_ops, "max_ops")
        c.bsgs_table_size = _lib.u64(self.bsgs_table_size, "bsgs_table_size")
        c.rho_r = _lib.u32(self.rho_r, "rho_r")
        c.rho_dp_bits = _lib.i32(self.rho_dp_bits, "rho_dp_bits")
        c.rho_walks_per_thread = _lib.u32(self.rho_walks_per_thread, "rho_walks_per_thread")
        c.rho_negation_map = 1 if self.rho_negation_map else 0
        c.rho_max_table_entries = _lib.u64(self.rho_max_table_entries, "rho_max_table_entries")
        c.kangaroo_herd_size = _lib.u32(self.kangaroo_herd_size, "kangaroo_herd_size")
        c.kangaroo_dp_bits = _lib.i32(self.kangaroo_dp_bits, "kangaroo_dp_bits")
        c.kangaroo_jumps = _lib.u32(self.kangaroo_jumps, "kangaroo_jumps")
        c.grumpy_m = _lib.u64(self.grumpy_m, "grumpy_m")
        c.grumpy_alpha = float(self.grumpy_alpha)
        c.solver = int(Solver(self.solver))
        c.bsgs_max_prime = _lib.u64(self.bsgs_max_prime, "bsgs_max_prime")
        return c


@dataclass(frozen=True)
class Stats:
    """Work statistics (``ca_stats``) reported by every solver."""

    group_ops: int = 0  # group operations performed (adds/muls)
    iterations: int = 0  # algorithm-specific step counter
    table_entries: int = 0  # entries stored in lookup tables
    collisions: int = 0  # useful collisions / relations found
    bytes_peak: int = 0  # approximate peak heap usage of tables
    seconds: float = 0.0  # wall-clock time spent
    threads: int = 0  # threads used

    @classmethod
    def from_c(cls, c: CStats) -> "Stats":
        return cls(
            group_ops=c.group_ops,
            iterations=c.iterations,
            table_entries=c.table_entries,
            collisions=c.collisions,
            bytes_peak=c.bytes_peak,
            seconds=c.seconds,
            threads=c.threads,
        )


# --------------------------------------------------------------------------
# Index calculus
# --------------------------------------------------------------------------


@dataclass
class ICParams:
    """Index-calculus parameters mirroring ``ca_ic_params`` (0 => auto)."""

    method: ICMethod = ICMethod.LINEAR_SIEVE
    factor_base_bound: int = 0  # B; 0 => auto from the size of p
    sieve_radius: int = 0  # C (linear sieve only); 0 => auto
    threads: int = 1  # relation collection threads (0 => 1)
    extra_relations: int = 0  # relations beyond #unknowns; 0 => auto
    seed: int = 0  # 0 => random
    max_relation_tries: int = 0  # random-exponent method: abort bound (0 = none)
    verbose: bool = False  # stage reports on stderr

    @classmethod
    def library_defaults(cls) -> "ICParams":
        c = CICParams()
        _lib.lib.ca_ic_params_default(ctypes.byref(c))
        return cls.from_c(c)

    @classmethod
    def from_c(cls, c: CICParams) -> "ICParams":
        return cls(
            method=ICMethod(c.method),
            factor_base_bound=c.factor_base_bound,
            sieve_radius=c.sieve_radius,
            threads=c.threads,
            extra_relations=c.extra_relations,
            seed=c.seed,
            max_relation_tries=c.max_relation_tries,
            verbose=bool(c.verbose),
        )

    def to_c(self) -> CICParams:
        c = CICParams()
        _lib.lib.ca_ic_params_default(ctypes.byref(c))
        c.method = int(ICMethod(self.method))
        c.factor_base_bound = _lib.u32(self.factor_base_bound, "factor_base_bound")
        c.sieve_radius = _lib.u32(self.sieve_radius, "sieve_radius")
        c.threads = _lib.u32(self.threads, "threads")
        c.extra_relations = _lib.u32(self.extra_relations, "extra_relations")
        c.seed = _lib.u64(self.seed, "seed")
        c.max_relation_tries = _lib.u64(self.max_relation_tries, "max_relation_tries")
        c.verbose = 1 if self.verbose else 0
        return c


@dataclass(frozen=True)
class ICStats:
    """Index-calculus statistics (``ca_ic_stats``)."""

    factor_base_size: int = 0
    unknowns: int = 0
    relations: int = 0
    verified_logs: int = 0
    sieve_candidates: int = 0
    smooth_tests: int = 0
    sieve_seconds: float = 0.0
    linalg_seconds: float = 0.0
    total_seconds: float = 0.0
    lanczos_iterations: int = 0
    threads: int = 0

    @classmethod
    def from_c(cls, c: CICStats) -> "ICStats":
        return cls(**{f.name: getattr(c, f.name) for f in fields(cls)})


__all__ = [
    "Elem",
    "ElemLike",
    "GroupKind",
    "ICMethod",
    "ICParams",
    "ICStats",
    "Options",
    "Solver",
    "Stats",
]
