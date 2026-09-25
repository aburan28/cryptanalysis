"""Factor-base subspaces V of F_2^n, their exact point sets, and structural invariants.

A factor base is F_V = {P in E(F_2^n) : x(P) in V} for an l-dimensional F_2-subspace V.
Families compared at matched (n, l):

  prefix     span{1, z, ..., z^(l-1)}, the literature's choice
  geometric  c * span{1, g, ..., g^(l-1)} for random c != 0, g not in F_2
  geomtrace  a geometric progression inside ker(Tr): c is drawn from the (n - l)-dimensional
             solution space of Tr(c g^j) = 0, so the base has the minimal product profile
             and every point lies in 2E (the kertrace yield)
  random     a uniformly random l-dimensional subspace
  normal     span{beta, beta^2, ..., beta^(2^(l-1))}, consecutive conjugates of a normal element
  kertrace   a random l-dimensional subspace of ker(Tr)
  invariant  a Frobenius-stable subspace (V^2 = V); exists only when l is a sum of
             degrees of irreducible factors of x^n - 1 over F_2

Product profile.  V^(k) is the F_2-span of all k-fold products of elements of V.  For
prime n no proper subfield exists, so dim V^(k) >= min(n, k(l-1)+1) (Hou-Leung-Xiang's
field analogue of Kneser's theorem) and, below n - 1, the bound is attained only by
geometric progressions (Bachoc-Serra-Zemor's analogue of Vosper's theorem).  The
symmetric functions e_k of m factor-base abscissae live in V^(k), so this profile is the
cheap structural quantity behind the PDP's linearization excess (see descent.py).

Subgroup policy.  A point P is usable when its r-component pi_r(P) = [h (h^-1 mod r)]P is
not the identity; its relation-matrix column is the +-orbit of pi_r(P) (and, for a
Frobenius-stable V on the Koblitz curve, the tau-orbit as well).  The strict policy
(P itself in <G>) is also counted.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

import kernel
from toycurve import ToyCurve, sha256_hex

FAMILIES = ("prefix", "geometric", "geomtrace", "random", "normal", "kertrace", "invariant")


# --------------------------------------------------------------- F_2 linear algebra
def reduce_basis(vectors) -> list[int]:
    """An echelon basis (by highest bit) of the F_2-span of integer bit vectors."""
    basis: dict[int, int] = {}
    for v in vectors:
        v = int(v)
        while v:
            h = v.bit_length() - 1
            if h in basis:
                v ^= basis[h]
            else:
                basis[h] = v
                break
    return list(basis.values())


def rank(vectors) -> int:
    return len(reduce_basis(vectors))


def span(basis: list[int]) -> np.ndarray:
    """All 2^l elements, element[mask] = XOR of basis[j] over the set bits j of mask."""
    out = np.zeros(1 << len(basis), dtype=np.uint64)
    for j, b in enumerate(basis):
        out[1 << j : 2 << j] = out[: 1 << j] ^ np.uint64(b)
    return out


def kernel_basis(columns: list[int], n: int) -> list[int]:
    """Basis of {x : M x = 0} where column j of the n x n matrix M is columns[j]."""
    rows = [0] * n
    for j, col in enumerate(columns):
        for i in range(n):
            if (col >> i) & 1:
                rows[i] |= 1 << j
    pivots: list[tuple[int, int]] = []
    rows = [r for r in rows]
    used = []
    for col in range(n):
        piv = next((i for i in range(len(rows)) if i not in used and (rows[i] >> col) & 1), None)
        if piv is None:
            continue
        used.append(piv)
        for i in range(len(rows)):
            if i != piv and (rows[i] >> col) & 1:
                rows[i] ^= rows[piv]
        pivots.append((col, piv))
    pivot_cols = {c for c, _ in pivots}
    free = [c for c in range(n) if c not in pivot_cols]
    out = []
    for f in free:
        v = 1 << f
        for c, p in pivots:
            if (rows[p] >> f) & 1:
                v |= 1 << c
        out.append(v)
    return out


def _columns_of_rows(rows: list[int], n: int) -> list[int]:
    """Transpose: the n columns (as bit vectors over the rows) of a matrix given by rows."""
    return [sum(((r >> j) & 1) << i for i, r in enumerate(rows)) for j in range(n)]


# --------------------------------------------------------------- subspace families
def _random_independent(rng: random.Random, n: int, l: int, pred=lambda x: True) -> list[int]:
    while True:
        cand = []
        while len(cand) < l:
            x = rng.getrandbits(n)
            if x and pred(x):
                cand.append(x)
        if rank(cand) == l:
            return cand


def _is_prime(n: int) -> bool:
    return n > 1 and all(n % p for p in range(2, int(n**0.5) + 1))


def cyclotomic_factors(n: int) -> tuple[int, list[int]]:
    """(k, factors): the irreducible factors over F_2 of Phi_n = (x^n - 1)/(x - 1) for an
    odd prime n, each of degree k = ord_n(2), as integers (bit i = coefficient of x^i)."""
    import gf2n

    k = 1
    while pow(2, k, n) != 1:
        k += 1
    Fk = gf2n.GF2n(k)
    rng = random.Random(n)
    while True:
        zeta = Fk.pow(Fk.random(rng) or 1, (2**k - 1) // n)
        if zeta != 1:
            break
    seen: set[int] = set()
    factors = []
    for t in range(1, n):
        if t in seen:
            continue
        coset = {t * pow(2, i, n) % n for i in range(k)}
        seen |= coset
        z = Fk.pow(zeta, t)
        poly = [1]
        for i in range(k):
            root = Fk.frob(z, i)
            nxt = [0] * (len(poly) + 1)
            for d, c in enumerate(poly):
                nxt[d] ^= Fk.mul(c, root)
                nxt[d + 1] ^= c
            poly = nxt
        assert all(c in (0, 1) for c in poly), "minimal polynomial not over F_2"
        factors.append(sum(c << i for i, c in enumerate(poly)))
    return k, factors


def frobenius_invariant_basis(curve: ToyCurve, l: int, rng: random.Random) -> list[int] | None:
    """An l-dimensional squaring-stable subspace, or None if none exists.

    F_2^n is the F_2[sigma]-module F_2[x]/(x^n - 1) (normal basis theorem), so its
    sigma-stable subspaces are the kernels of p(sigma) for divisors p of x^n - 1.  For
    prime n these have dimension a*k + b with k = ord_n(2), b in {0, 1} (b = 1 adds F_2).
    """
    n, K = curve.n, curve.K
    if not _is_prime(n) or n == 2:
        return None
    k, factors = cyclotomic_factors(n)
    choices = [(a, b) for a in range(len(factors) + 1) for b in (0, 1) if a * k + b == l]
    if not choices or l == 0:
        return None
    a, b = choices[0]
    picked = rng.sample(factors, a)
    basis: list[int] = []
    for p in picked:
        cols = []
        for j in range(n):
            acc = 0
            for i in range(p.bit_length()):
                if (p >> i) & 1:
                    acc ^= K.frob(1 << j, i)
            cols.append(acc)
        ker = kernel_basis(cols, n)
        assert len(ker) == k
        basis += ker
    if b:
        basis.append(1)
    assert rank(basis) == l
    assert rank(basis + [K.sqr(v) for v in basis]) == l, "subspace is not squaring-stable"
    return basis


def family_basis(curve: ToyCurve, family: str, l: int, seed: int) -> tuple[list[int], dict]:
    n, K = curve.n, curve.K
    rng = random.Random(f"{family}|{n}|{l}|{seed}")
    params: dict = {"seed": seed}
    if family == "prefix":
        basis = [1 << j for j in range(l)]
        params = {"c": 1, "g": 2}
    elif family == "geometric":
        c = rng.randrange(1, 1 << n)
        while True:
            g = rng.randrange(2, 1 << n)
            basis = [K.mul(c, K.pow(g, j)) for j in range(l)]
            if rank(basis) == l:
                break
        params.update({"c": c, "g": g})
    elif family == "geomtrace":
        # c * span{1, g, ..., g^(l-1)} inside ker(Tr): Tr(c g^j) = 0 is l linear conditions on c
        while True:
            g = rng.randrange(2, 1 << n)
            powers = [K.pow(g, j) for j in range(l)]
            if rank(powers) < l:
                continue
            conds = [sum(K.trace(K.mul(1 << i, p)) << i for i in range(n)) for p in powers]
            ker = kernel_basis(_columns_of_rows(conds, n), n)
            c = 0
            while not c:
                c = sum(v for v in ker if rng.getrandbits(1))
            basis = [K.mul(c, p) for p in powers]
            if rank(basis) == l and all(K.trace(b) == 0 for b in basis):
                break
        params.update({"c": c, "g": g})
    elif family == "random":
        basis = _random_independent(rng, n, l)
    elif family == "kertrace":
        basis = _random_independent(rng, n, l, lambda x: K.trace(x) == 0)
    elif family == "normal":
        while True:
            beta = rng.getrandbits(n)
            conj = [K.frob(beta, j) for j in range(n)]
            if rank(conj) == n:
                break
        basis = conj[:l]
        params.update({"beta": beta})
    elif family == "invariant":
        basis = frobenius_invariant_basis(curve, l, rng)
        if basis is None:
            raise ValueError(f"no {l}-dimensional Frobenius-stable subspace for n={n}")
    else:
        raise ValueError(f"unknown family {family}")
    assert rank(basis) == l
    return basis, params


# --------------------------------------------------------------- invariants
def product_profile(K: kernel.Field, basis: list[int], kmax: int) -> list[int]:
    """[dim V^(1), ..., dim V^(kmax)]."""
    dims = []
    cur = reduce_basis(basis)
    dims.append(len(cur))
    for _ in range(2, kmax + 1):
        cur = reduce_basis(K.mul(p, v) for p in cur for v in basis)
        dims.append(len(cur))
    return dims


def minimal_profile(n: int, l: int, kmax: int) -> list[int]:
    return [min(n, k * (l - 1) + 1) for k in range(1, kmax + 1)]


@dataclass
class FactorBase:
    curve: ToyCurve
    family: str
    l: int
    seed: int = 0
    basis: list[int] = field(default_factory=list)
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.basis:
            self.basis, self.params = family_basis(self.curve, self.family, self.l, self.seed)
        c, K = self.curve, self.curve.K
        self.elements = span(self.basis)
        ys, ok = K.lift_batch(self.elements)
        xs = self.elements[ok]
        ys = ys[ok]
        self.liftable = int(ok.sum())
        neg = xs ^ ys
        two_sided = xs != 0
        self.xs = np.concatenate([xs, xs[two_sided]])
        self.ys = np.concatenate([ys, neg[two_sided]])
        order = np.lexsort((self.ys, self.xs))
        self.xs, self.ys = self.xs[order], self.ys[order]
        self.coords = {int(x): j for j, x in enumerate(self.elements.tolist())}
        px, py = c.project(self.xs, self.ys)
        self.px, self.py = px, py
        self.usable = px != np.uint64(kernel.INF_X)
        sx, _ = c.psi(self.xs, self.ys)
        self.strict = (sx == np.uint64(kernel.INF_X)) & self.usable
        self.frobenius_stable = rank(self.basis + [K.sqr(v) for v in self.basis]) == self.l
        self._columns()

    def _columns(self) -> None:
        """Relation-matrix columns: +-orbits of pi_r(P) (and tau-orbits when V^2 = V)."""
        c, K = self.curve, self.curve.K
        keys: dict[int, int] = {}
        col_of = np.full(len(self.xs), -1, dtype=np.int64)
        coeff = np.zeros(len(self.xs), dtype=object)
        lam = c.frobenius_eigenvalue() if self.frobenius_stable else None
        reps: list[tuple[int, int]] = []
        for i in range(len(self.xs)):
            if not self.usable[i]:
                continue
            Q = (int(self.px[i]), int(self.py[i]))
            if lam is None:
                key = Q[0]
                if key not in keys:
                    keys[key] = len(reps)
                    reps.append((Q[0], min(Q[1], Q[0] ^ Q[1])))
                j = keys[key]
                coeff[i] = 1 if Q[1] == reps[j][1] else -1
                col_of[i] = j
            else:
                # walk the tau-orbit of Q; the canonical key is the least x over +-tau^t(Q)
                orbit_x = []
                x = Q[0]
                for _ in range(c.n):
                    orbit_x.append(x)
                    x = K.sqr(x)
                key = min(orbit_x)
                t = orbit_x.index(key)
                if key not in keys:
                    keys[key] = len(reps)
                    base = Q
                    for _ in range(t):
                        base = (K.sqr(base[0]), K.sqr(base[1]))
                    reps.append((base[0], min(base[1], base[0] ^ base[1])))
                j = keys[key]
                T = Q
                for _ in range(t):
                    T = (K.sqr(T[0]), K.sqr(T[1]))
                sign = 1 if T[1] == reps[j][1] else -1
                # tau^t(Q) = +-rep, so log Q = +-lambda^(-t) log rep
                coeff[i] = sign * pow(lam, -t, c.r) % c.r
                col_of[i] = j
        self.col_of = col_of
        self.col_coeff = coeff
        self.column_reps = reps

    # ------------------------------------------------------------------ counts
    @property
    def geometric_points(self) -> int:
        return int(len(self.xs))

    @property
    def usable_points(self) -> int:
        return int(self.usable.sum())

    @property
    def strict_points(self) -> int:
        return int(self.strict.sum())

    @property
    def effective_columns(self) -> int:
        return len(self.column_reps)

    def point_index(self) -> dict[tuple[int, int], int]:
        return {(int(x), int(y)): i for i, (x, y) in enumerate(zip(self.xs, self.ys))}

    def invariants(self, kmax: int = 4) -> dict:
        c, K = self.curve, self.curve.K
        n, l = c.n, self.l
        img = [K.sqr(v) for v in self.basis]
        z4 = c.z4_labels(self.xs, self.ys)
        prof = product_profile(K, self.basis, kmax)
        return {
            "product_profile": prof,
            "minimal_profile": minimal_profile(n, l, kmax),
            "product_excess": [a - b for a, b in zip(prof, minimal_profile(n, l, kmax))],
            "frobenius_overlap": 2 * l - rank(self.basis + img),
            "frobenius_stable": self.frobenius_stable,
            "trace_kernel_dim": l - (1 if any(K.trace(v) for v in self.basis) else 0),
            "liftable_fraction": self.liftable / (1 << l),
            "z4_class_counts": None if z4 is None else [z4.count(k) for k in range(4)],
        }

    # ------------------------------------------------------------------ identity
    def record(self) -> dict:
        """The AGENTS.md `factor_base` section (hash input excludes run data)."""
        usable = sorted(
            [int(x), int(y)] for x, y, u in zip(self.xs, self.ys, self.usable) if u
        )
        return {
            "curve_id": self.curve.curve_id,
            "construction": {
                "family": self.family,
                "basis": [int(b) for b in self.basis],
                "params": {k: int(v) for k, v in self.params.items()},
                "polynomial_constraint": "none",
                "shifted_bases": "none",
            },
            "subgroup_policy": "cofactor_projection",
            "enumerated_set_sha256": sha256_hex(usable),
            "nominal_dimension": self.l,
            "geometric_point_count": self.geometric_points,
            "actual_usable_point_count": self.usable_points,
            "strict_subgroup_point_count": self.strict_points,
            "quotient_rule": "sign+frobenius" if self.frobenius_stable else "sign",
            "effective_columns": self.effective_columns,
        }

    @property
    def digest(self) -> str:
        return sha256_hex(self.record())

    @property
    def label(self) -> str:
        return f"N{self.curve.n}{self.family}l{self.l}s{self.seed}"
