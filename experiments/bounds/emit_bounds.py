#!/usr/bin/env python3
"""Turn a `ca_bench --json` sweep into `ecbench.bound/v1` records.

`ca_bench complexity --json FILE` writes one JSON object per solved instance
with the raw `ca_stats` counters.  This script reads that file and writes one
sealed bound record per (algorithm, group kind, tier) in exactly the shape
ecbench's `bound fit` writes (`src/cryptanalysis/ecbench/bounds.rs` in
aburan28/crypto), so that `ecbench frontier build` accepts the records and
puts this library's constants on a page of their own, in their own unit
(`cryptanalysis.group_ops`), beside -- never mixed with -- `ecbench.gae`.

Everything that is an identity here mirrors the Rust: canonical JSON for
`domain_id` and `method_id` (sorted keys, compact, ASCII-escaped, no floats);
the document seal (`bound_id` is the SHA-256 of the pretty-printed document
with the field empty, where the pretty print is byte-identical to
`serde_json::to_string_pretty` plus a trailing newline); the two-stage
bootstrap and its seed.  `test_seal.py` proves the seal on two real ecbench
records.  README.md says what a record claims and what it does not.

    emit_bounds.py emit --sweep sweeps/complexity-DATE.jsonl --out records
    emit_bounds.py list records
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

SCHEMA = "ecbench.bound/v1"
BOUND_PREFIX = "ECBND1h"
DOMAIN_PREFIX = "ECDOM1"
METHOD_PREFIX = "ECM1"
METHOD_SCHEMA = "ecbench.method/v1"
SESSION_PREFIX = "CAB1h"
SPEC_PREFIX = "CAS1h"
ENV_PREFIX = "CAENV1h"
SWEEP_SCHEMA = "ca_bench.sweep/v1"

PROBLEM = "dlp.single_target"
UNIT = "cryptanalysis.group_ops"
RESAMPLES = 2000
SEED = 20261005
MIN_SIZES_FOR_SCALING = 4

# ca_bench's group kinds, as the domain names them, and the automorphisms the
# generic floor sqrt(pi / 2A) counts: negation on a curve, nothing in Z_p^*.
FAMILY = {"zp": "zp", "ec": "ec_prime"}
AUTOMORPHISMS = {"zp": 1, "ec": 2}
# `generic` mode names its two rho rows `rho-1` and `rho-T`; both are the same
# method, and `rho-T` is excluded by its thread count, not by its name.
ALIASES = {"rho-1": "rho", "rho-T": "rho"}

# The method a row was solved by: the library's entry point and the parameters
# `ca_bench` leaves at their defaults ("auto" where the solver derives them
# from the group order).  Parameters are strings, as in ecbench's registry.
METHODS: dict[str, dict[str, Any]] = {
    "bsgs": {
        "id": "ca.bsgs",
        "family": "bsgs",
        "entry": "ca_bsgs_solve",
        "params": {"table_size": "auto"},
    },
    "rho": {
        "id": "ca.rho",
        "family": "rho",
        "entry": "ca_rho_solve",
        "params": {
            "dp_bits": "auto",
            "negation_map": "1",
            "r": "auto",
            "threads": "1",
            "walks_per_thread": "auto",
        },
    },
    "kangaroo": {
        "id": "ca.kangaroo",
        "family": "kangaroo",
        "entry": "ca_kangaroo_solve",
        "params": {"dp_bits": "auto", "herd_size": "auto", "jumps": "auto"},
    },
    "grumpy": {
        "id": "ca.grumpy",
        "family": "grumpy",
        "entry": "ca_grumpy_solve",
        "params": {"alpha": "0.7", "m": "auto"},
    },
}


def declared_s(alg: str, group: str) -> float | None:
    """The documented constant of the method in S = group_ops / sqrt(N).

    README.md and docs/ALGORITHMS.md of this repository: BSGS `1.5 sqrt(N)`;
    rho `sqrt(pi N / 2)`, halved by sqrt(2) on a curve by the negation map
    the library uses there by default; kangaroo the textbook `2 sqrt(N)`;
    grumpy giants `1.18 sqrt(n)` in the whole group (the 400-instance
    simulation in ALGORITHMS.md).  None where nothing is documented.
    """
    if alg == "bsgs":
        return 1.5
    if alg == "rho":
        return math.sqrt(math.pi / 2) if group == "zp" else math.sqrt(math.pi / 4)
    if alg == "kangaroo":
        return 2.0
    if alg == "grumpy":
        return 1.18
    return None


# ── Canonical JSON and identities (canonical.rs) ────────────────────


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _refuse_floats(v: Any, where: str = "$") -> None:
    if isinstance(v, bool) or v is None or isinstance(v, (int, str)):
        return
    if isinstance(v, float):
        raise ValueError(f"float {v!r} at {where} in an identity; write it as a string")
    if isinstance(v, dict):
        for k, x in v.items():
            _refuse_floats(x, f"{where}.{k}")
        return
    if isinstance(v, (list, tuple)):
        for i, x in enumerate(v):
            _refuse_floats(x, f"{where}[{i}]")
        return
    raise TypeError(f"{type(v).__name__} at {where} has no canonical form")


def canonical(v: Any) -> str:
    """Keys sorted, no whitespace, non-ASCII escaped, floats refused."""
    _refuse_floats(v)
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def short_id(prefix: str, v: Any) -> str:
    """`prefix` + `h` + the first 12 hex digits of the canonical digest."""
    return f"{prefix}h{sha256_hex(canonical(v).encode('utf-8'))[:12]}"


def domain_id(domain: dict[str, Any]) -> str:
    return short_id(DOMAIN_PREFIX, domain)


def method_id(ident: str, params: dict[str, str]) -> str:
    return short_id(METHOD_PREFIX, {"schema": METHOD_SCHEMA, "id": ident, "params": params})


# ── serde_json's pretty printer, byte for byte ──────────────────────


def ryu_f64(x: float) -> str:
    """A finite f64 as serde_json writes it (the `ryu` crate's shortest form).

    Python's `repr` yields the same shortest round-trip digits; only the
    layout differs (`1e-05` against `0.00001`, `1e+16` against `1e16`), so
    the digits are taken from `repr` and laid out by ryu's rule: plain
    notation while the decimal point sits within (-5, 16] digits of the
    first significant digit, scientific notation otherwise, always with a
    fractional part or an exponent.
    """
    if not math.isfinite(x):
        raise ValueError("a non-finite float has no JSON number form")
    if x == 0.0:
        return "-0.0" if math.copysign(1.0, x) < 0 else "0.0"
    sign = "-" if x < 0 else ""
    text = repr(abs(x))
    mant, _, exp_text = text.partition("e")
    exp = int(exp_text) if exp_text else 0
    ip, _, fp = mant.partition(".")
    digits = (ip + fp).lstrip("0")
    k = exp - len(fp)
    kept = len(digits.rstrip("0"))
    k += len(digits) - kept
    digits = digits[:kept]
    length = len(digits)
    kk = length + k  # 10^(kk-1) <= |x| < 10^kk
    if 0 <= k and kk <= 16:
        body = digits + "0" * k + ".0"
    elif 0 < kk <= 16:
        body = digits[:kk] + "." + digits[kk:]
    elif -5 < kk <= 0:
        body = "0." + "0" * (-kk) + digits
    elif length == 1:
        body = f"{digits}e{kk - 1}"
    else:
        body = f"{digits[0]}.{digits[1:]}e{kk - 1}"
    return sign + body


_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def json_string(s: str) -> str:
    """A JSON string as serde_json writes it: `"`, `\\` and control
    characters escaped, everything else (non-ASCII included) raw."""
    out = ['"']
    for ch in s:
        esc = _SHORT_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _write_pretty(v: Any, out: list[str], depth: int) -> None:
    if v is None:
        out.append("null")
    elif v is True:
        out.append("true")
    elif v is False:
        out.append("false")
    elif isinstance(v, int):
        out.append(str(v))
    elif isinstance(v, float):
        out.append(ryu_f64(v))
    elif isinstance(v, str):
        out.append(json_string(v))
    elif isinstance(v, (list, tuple)):
        if not v:
            out.append("[]")
            return
        out.append("[")
        for i, item in enumerate(v):
            out.append(",\n" if i else "\n")
            out.append("  " * (depth + 1))
            _write_pretty(item, out, depth + 1)
        out.append("\n" + "  " * depth + "]")
    elif isinstance(v, dict):
        if not v:
            out.append("{}")
            return
        out.append("{")
        for i, key in enumerate(sorted(v)):
            if not isinstance(key, str):
                raise TypeError(f"object key {key!r} is not a string")
            out.append(",\n" if i else "\n")
            out.append("  " * (depth + 1))
            out.append(json_string(key))
            out.append(": ")
            _write_pretty(v[key], out, depth + 1)
        out.append("\n" + "  " * depth + "}")
    else:
        raise TypeError(f"{type(v).__name__} has no JSON form")


def dumps_pretty(v: Any) -> str:
    """`serde_json::to_string_pretty` of a `Value` whose maps are BTreeMaps:
    two-space indent, `"key": value`, keys sorted, one array element per
    line, `[]` and `{}` for empty containers, no trailing newline."""
    out: list[str] = []
    _write_pretty(v, out, 0)
    return "".join(out)


def seal(
    doc: dict[str, Any], field: str = "bound_id", prefix: str = BOUND_PREFIX
) -> tuple[str, str]:
    """`seal_document`: the id is `prefix` + 12 hex of the SHA-256 of the
    pretty text with `field` empty; returns the id and the sealed text."""
    if field not in doc:
        raise ValueError(f"document has no `{field}` field to seal")
    blank_doc = dict(doc)
    blank_doc[field] = ""
    blank = dumps_pretty(blank_doc) + "\n"
    needle = f'"{field}": ""'
    if blank.count(needle) != 1:
        raise ValueError(f"the `{field}` field must appear exactly once in the document")
    ident = prefix + sha256_hex(blank.encode("utf-8"))[:12]
    return ident, blank.replace(needle, f'"{field}": "{ident}"', 1)


def check_seal(text: str, field: str = "bound_id", prefix: str = BOUND_PREFIX) -> str:
    """`check_document_seal`: whether `text` hashes to the id it carries."""
    doc = json.loads(text)
    ident = doc.get(field)
    if not isinstance(ident, str):
        raise ValueError(f"no `{field}`")
    if not ident.startswith(prefix):
        raise ValueError(f"`{field}` {ident} does not start with {prefix}")
    filled = f'"{field}": "{ident}"'
    if text.count(filled) != 1:
        raise ValueError(f"`{field}` must appear exactly once as written")
    blank = text.replace(filled, f'"{field}": ""', 1)
    expect = prefix + sha256_hex(blank.encode("utf-8"))[:12]
    if expect != ident:
        raise ValueError(f"seal mismatch: bytes hash to {expect}, document says {ident}")
    return ident


# ── Statistics (stats.rs, bounds.rs) ───────────────────────────────

_MASK = (1 << 64) - 1


def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & _MASK
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
    return z ^ (z >> 31)


class Resampler:
    """ecbench's resampling generator: splitmix64 over its own state."""

    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK

    def below(self, n: int) -> int:
        self.state = splitmix64(self.state)
        return self.state % n


def mean(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    total = 0.0
    for x in xs:  # left to right, as the Rust sums
        total += x
    return total / len(xs)


def quantile(xs: Sequence[float], q: float) -> float | None:
    if not xs:
        return None
    v = sorted(xs)
    pos = min(max(q, 0.0), 1.0) * (len(v) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


Stat = Callable[[list[list[Any]]], "float | None"]


def _resample(
    strata: Sequence[Sequence[Any]], resamples: int, seed: int, clusters: bool, stat: Stat
) -> tuple[float, float] | None:
    if not strata or any(len(s) == 0 for s in strata):
        return None
    rng = Resampler(seed)
    k = len(strata)
    values: list[float] = []
    for _ in range(resamples):
        picked = [strata[rng.below(k)] for _ in range(k)] if clusters else list(strata)
        draw = [[s[rng.below(len(s))] for _ in range(len(s))] for s in picked]
        v = stat(draw)
        if v is not None and math.isfinite(v):
            values.append(v)
    if len(values) < resamples * 9 // 10:
        return None
    lo = quantile(values, 0.025)
    hi = quantile(values, 0.975)
    if lo is None or hi is None:
        return None
    return lo, hi


def bootstrap_ci(strata: Sequence[Sequence[Any]], resamples: int, seed: int, stat: Stat):
    """Percentile bootstrap within fixed strata."""
    return _resample(strata, resamples, seed, False, stat)


def cluster_bootstrap_ci(strata: Sequence[Sequence[Any]], resamples: int, seed: int, stat: Stat):
    """Two-stage bootstrap: strata with replacement, then items within each."""
    if len(strata) < 2:
        return None
    return _resample(strata, resamples, seed, True, stat)


def ols(points: Sequence[tuple[float, float]]) -> tuple[float, float, float] | None:
    """Least squares of y = alpha x + b: (alpha, b, R^2); None below two distinct x.

    The distinct-x test is explicit: with every point at one size the
    normal-equation denominator is a rounding residue, not zero, and the
    quotient of two residues is not an exponent.
    """
    n = len(points)
    if n < 2 or len({x for x, _ in points}) < 2:
        return None
    sx = sy = sxx = sxy = 0.0
    for x, y in points:
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    alpha = (n * sxy - sx * sy) / denom
    b = (sy - alpha * sx) / n
    ybar = sy / n
    ss_res = ss_tot = 0.0
    for x, y in points:
        yh = alpha * x + b
        ss_res += (y - yh) * (y - yh)
        ss_tot += (y - ybar) * (y - ybar)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0
    return alpha, b, r2


def power_law(strata: Sequence[Sequence[tuple[float, float]]], resamples: int, seed: int):
    """cost = C r^alpha over strata of (ln r, ln cost): alpha, its two-stage
    interval, log2 C, R^2 and the interval's method."""
    all_points = [p for s in strata for p in s]
    fit = ols(all_points)
    if fit is None:
        return None, None, None, None, "none"
    alpha, b, r2 = fit

    def slope(s: list[list[tuple[float, float]]]) -> float | None:
        f = ols([p for stratum in s for p in stratum])
        return f[0] if f else None

    nonempty = [list(s) for s in strata if s]
    if len(nonempty) >= 2:
        ci, method = cluster_bootstrap_ci(nonempty, resamples, seed, slope), "cluster"
    else:
        ci, method = None, "none"
    return alpha, ci, b / math.log(2.0), r2, method


@dataclass
class Estimate:
    value: float
    ci95: tuple[float, float] | None
    ci_method: str

    def as_json(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "ci95": list(self.ci95) if self.ci95 else None,
            "ci_method": self.ci_method,
        }


def estimate(strata: Sequence[Sequence[float]], resamples: int, seed: int) -> Estimate | None:
    """Mean over strata with its two-stage interval; within-stratum when
    there is one stratum."""
    all_values = [x for s in strata for x in s]
    value = mean(all_values)
    if value is None:
        return None

    def stat(s: list[list[float]]) -> float | None:
        return mean([x for stratum in s for x in stratum])

    nonempty = [list(s) for s in strata if s]
    if len(nonempty) >= 2:
        return Estimate(value, cluster_bootstrap_ci(nonempty, resamples, seed, stat), "cluster")
    return Estimate(value, bootstrap_ci(nonempty, resamples, seed, stat), "within")


# ── The sweep ──────────────────────────────────────────────────────


def tier_of_bits(field_bits: int) -> str:
    """crypto-autoresearcher's claim tiers: toy to 32 bits, medium to 96, crypto above."""
    if field_bits <= 32:
        return "toy"
    if field_bits <= 96:
        return "medium"
    return "crypto"


def floor_s(automorphisms: int) -> float:
    """sqrt(pi / 2A): the generic collision-search floor in S."""
    return math.sqrt(math.pi / (2.0 * max(automorphisms, 1)))


def read_sweep(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    header: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            kind = obj.get("record")
            if kind == "header":
                if header is not None:
                    raise SystemExit(f"{path}:{lineno}: a second header line")
                header = obj
            elif kind == "instance":
                rows.append(obj)
            else:
                raise SystemExit(f"{path}:{lineno}: unknown record kind {kind!r}")
    if header is None:
        raise SystemExit(f"{path}: no header line; was it written by `ca_bench --json`?")
    if header.get("schema") != SWEEP_SCHEMA:
        raise SystemExit(f"{path}: schema {header.get('schema')!r}, expected {SWEEP_SCHEMA}")
    return header, rows


def session_ref(header: dict[str, Any], sweep: Path, root: Path) -> dict[str, Any]:
    """The sweep file as a session: named by its own hash, its command line
    and its host, the way ecbench names a session, a spec and an environment."""
    data = sweep.read_bytes()
    sha = sha256_hex(data)
    cmd = header.get("command_line") or ""
    host = header.get("host") or ""
    try:
        rel = sweep.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = sweep.as_posix()
    return {
        "dir": rel,
        "session_id": SESSION_PREFIX + sha[:12],
        "spec_id": SPEC_PREFIX + sha256_hex(cmd.encode("utf-8"))[:12],
        "status": "complete",
        "arm": "",
        "role": "candidate",
        "binary_sha256": header.get("binary_sha256"),
        "git_commit": header.get("git_commit"),
        "env_class_id": ENV_PREFIX + sha256_hex(host.encode("utf-8"))[:12],
        "records_sha256": sha,
    }


@dataclass
class Bound:
    name: str
    bound_id: str
    text: str
    doc: dict[str, Any]


def _distinct_targets(rows: Sequence[dict[str, Any]]) -> int:
    keys = {(r.get("x"), r.get("instance")) if r.get("x") is None else r["x"] for r in rows}
    return len(keys)


def bound_of(
    alg: str,
    group: str,
    tier: str,
    rows: Sequence[dict[str, Any]],
    session: dict[str, Any],
    resamples: int,
    seed: int,
) -> Bound | None:
    """One record: `bound_from_sessions` with ca_bench rows for records,
    sizes for curves and instances for workloads."""
    meth = METHODS[alg]
    method = {
        "id": meth["id"],
        "params": dict(meth["params"]),
        "method_id": method_id(meth["id"], meth["params"]),
        "family": meth["family"],
        "entry": meth["entry"],
    }
    domain = {
        "problem": PROBLEM,
        "family": FAMILY[group],
        "target_kind": "planted",
        "unit": UNIT,
        "tier": tier,
        "envelope": {"targets": 1, "precomputation": "none", "threads": 1},
    }
    automorphisms = AUTOMORPHISMS[group]
    floor = floor_s(automorphisms)
    declared = declared_s(alg, group)

    by_n: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        by_n.setdefault(int(r["n"]), []).append(r)

    sizes: list[dict[str, Any]] = []
    strata: list[list[tuple[float, float]]] = []
    s_strata: list[list[float]] = []
    f_strata: list[list[float]] = []
    m_strata: list[list[float]] = []
    u_strata: list[list[float]] = []
    memory_known = True
    verified_total = 0
    for n in sorted(by_n):
        rs = by_n[n]
        bits_seen = {int(r["bits"]) for r in rs}
        if len(bits_seen) != 1:
            raise SystemExit(f"group order {n} appears with field sizes {sorted(bits_seen)}")
        bits = bits_seen.pop()
        ok = [r for r in rs if r.get("ok") is True]
        verified_total += len(ok)
        sq = math.sqrt(float(n))
        ln_r = math.log(float(n))
        ops = [float(int(r["group_ops"])) for r in ok]
        s_vals = [g / sq for g in ops]
        # Within a size the strata are the instances: each is one planted
        # target, which is what ecbench's workloads are.
        s_est = estimate([[s] for s in s_vals], resamples, seed)
        mems = [int(r["table_entries"]) / sq for r in ok if "table_entries" in r]
        if len(mems) != len(ok):
            memory_known = False
        sizes.append(
            {
                "slug": f"ca-{group}-{bits}",
                "log2_r": math.log2(float(n)),
                "r": n if n < (1 << 64) else str(n),
                "field_bits": bits,
                "automorphisms_available": automorphisms,
                "floor_s": floor,
                "workloads": _distinct_targets(rs),
                "runs": len(rs),
                "verified": len(ok),
                "mean_gae": mean(ops),
                "mean_s": s_est.value if s_est else None,
                "s_ci95": list(s_est.ci95) if s_est and s_est.ci95 else None,
                "ratio_to_floor": s_est.value / floor if s_est else None,
                "declared_s": declared,
                "declared_ratio_to_floor": declared / floor if declared is not None else None,
                "memory_entries_per_sqrt_r": mean(mems) if len(mems) == len(ok) else None,
                # The sum over the counters the unit declares unpriced, of
                # which this library has none: 0.0 by construction, as
                # ecbench reports a method without `*_uncharged` counters.
                "uncharged_per_sqrt_r": 0.0 if ok else None,
                "levels": {"L0": len(rs)},
            }
        )
        strata.append([(ln_r, math.log(g)) for g in ops if g > 0.0])
        s_strata.append(s_vals)
        f_strata.append([s / floor for s in s_vals])
        m_strata.append(mems)
        u_strata.append([0.0 for _ in ok])

    if verified_total == 0:
        return None

    n_sizes = sum(1 for s in sizes if s["verified"] > 0)
    alpha, alpha_ci, log2_c, r2, ci_method = power_law(strata, resamples, seed)
    declared_alpha = 0.5 if declared is not None else None
    scaling_claim = n_sizes >= MIN_SIZES_FOR_SCALING and alpha is not None
    agrees = None
    if declared_alpha is not None and alpha_ci is not None:
        agrees = alpha_ci[0] <= declared_alpha <= alpha_ci[1]
    fit = {
        "size_parameter": "r",
        "model": "gae = C * r^alpha",
        "points": sum(len(s) for s in strata),
        "sizes": n_sizes,
        "alpha": alpha,
        "alpha_ci95": list(alpha_ci) if alpha_ci else None,
        "log2_c": log2_c,
        "r_squared": r2,
        "ci_method": ci_method,
        "declared_alpha": declared_alpha,
        "alpha_agrees_with_declared": agrees,
        "scaling_claim": scaling_claim,
    }

    s_est = estimate(s_strata, resamples, seed ^ 0x5)
    f_est = estimate(f_strata, resamples, seed ^ 0xF)
    assert s_est is not None and f_est is not None
    declared_ratios = [
        s["declared_ratio_to_floor"] for s in sizes if s["declared_ratio_to_floor"] is not None
    ]
    declared_ratio = None
    if len(declared_ratios) == len(sizes) and all(
        abs(d - declared_ratios[0]) < 1e-9 for d in declared_ratios
    ):
        declared_ratio = declared_ratios[0]
    constant = {
        "s": s_est.as_json(),
        "ratio_to_floor": f_est.as_json(),
        "declared_ratio_to_floor": declared_ratio,
    }

    m_est = estimate(m_strata, resamples, seed ^ 0x3) if memory_known else None
    u_est = estimate(u_strata, resamples, seed ^ 0x7)
    dimensions = {
        "ops": {
            "statistic": "mean S / sqrt(pi / 2A) over verified runs",
            "source": "ca_stats.group_ops, the group order N, automorphisms_available",
            "lower_is_better": True,
            "known": math.isfinite(f_est.value),
            "value": f_est.value if math.isfinite(f_est.value) else None,
            "ci95": list(f_est.ci95) if f_est.ci95 else None,
        },
        "memory": {
            "statistic": "mean table entries / sqrt(r) over verified runs",
            "source": "ca_stats.table_entries",
            "lower_is_better": True,
            "known": m_est is not None,
            "value": m_est.value if m_est else None,
            "ci95": list(m_est.ci95) if m_est and m_est.ci95 else None,
        },
        "uncharged": {
            "statistic": "mean sum of *_uncharged counters / sqrt(r) over verified runs",
            "source": "none: libcryptanalysis counts no work it does not charge (README.md)",
            "lower_is_better": True,
            "known": u_est is not None,
            "value": u_est.value if u_est else None,
            "ci95": list(u_est.ci95) if u_est and u_est.ci95 else None,
        },
    }

    # One phase: the library reports the whole solve as one count.
    all_ops = [
        float(int(r["group_ops"])) for n in sorted(by_n) for r in by_n[n] if r.get("ok") is True
    ]
    total = sum(all_ops)
    sizes_with_work = sum(1 for s in strata if s)
    if sizes_with_work >= MIN_SIZES_FOR_SCALING:
        st_alpha, st_ci, _, _, _ = power_law(strata, resamples, seed ^ 0x51)
    else:
        st_alpha, st_ci = None, None
    stages = [
        {
            "name": "search",
            "mean_gae": total / verified_total,
            "share_of_gae": 1.0 if total > 0.0 else 0.0,
            "sizes_with_work": sizes_with_work,
            "alpha": st_alpha,
            "alpha_ci95": list(st_ci) if st_ci else None,
        }
    ]

    unverified = len(rows) - verified_total
    statuses: dict[str, int] = {}
    if verified_total:
        statuses["verified"] = verified_total
    if unverified:
        statuses["unverified"] = unverified
    reasons: list[str] = []
    if unverified > 0:
        reasons.append(
            f"{unverified} of {len(rows)} measured runs did not verify; only a wholly verified arm is admissible"
        )
    if not scaling_claim:
        reasons.append(
            f"{n_sizes} size(s): below {MIN_SIZES_FOR_SCALING}, so the exponent is descriptive and this is a constant bound"
        )
    sess = dict(session)
    sess["arm"] = alg
    provenance = {
        "sessions": [sess],
        "audits": [],
        "records": len(rows),
        "verified": verified_total,
        "statuses": statuses,
    }
    admissibility = {
        "status": "admissible" if unverified == 0 else "inadmissible",
        "bounded": False,
        "unpriced": [],
        "deterministic": True,
        "reasons": reasons,
    }
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "bound_id": "",
        "label": f"{meth['id']} on {n_sizes} {FAMILY[group]} groups, {tier} tier",
        "domain": domain,
        "domain_id": domain_id(domain),
        "method": method,
        "level": "exponent" if scaling_claim else "constant",
        "sizes": sizes,
        "fit": fit,
        "constant": constant,
        "dimensions": dimensions,
        "stages": stages,
        "provenance": provenance,
        "admissibility": admissibility,
        "fit_options": {"tier": tier, "curves": [], "resamples": resamples, "seed": seed},
        "improves_on": [],
        "verdict_id": None,
        "notes": (
            f"Unit {UNIT}: ca_stats.group_ops as libcryptanalysis counts it, from a "
            "`ca_bench --json` sweep; not comparable with ecbench.gae. Intervals are this "
            "adapter's bootstrap (experiments/bounds/README.md); `bound check` does not apply."
        ),
    }
    bound_id, text = seal(doc, "bound_id", BOUND_PREFIX)
    doc["bound_id"] = bound_id
    return Bound(f"ca-{group}-{alg}-{tier}.json", bound_id, text, doc)


def build_bounds(
    header: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    sweep: Path,
    root: Path,
    resamples: int = RESAMPLES,
    seed: int = SEED,
) -> tuple[list[Bound], Counter]:
    """Every (algorithm, group kind, tier) in the sweep as a bound, plus what
    was left out and why."""
    skipped: Counter = Counter()
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        name = row["algorithm"]
        alg = ALIASES.get(name, name)
        if alg not in METHODS:
            skipped[f"algorithm {name!r} has no method here"] += 1
            continue
        if int(row.get("threads", 1)) != 1:
            skipped[f"{name!r} rows with threads != 1 (the envelope is one thread)"] += 1
            continue
        group = row["group"]
        if group not in FAMILY:
            raise SystemExit(f"unknown group kind {group!r}")
        groups.setdefault((alg, group, tier_of_bits(int(row["bits"]))), []).append(row)
    session = session_ref(header, sweep, root)
    bounds: list[Bound] = []
    for (alg, group, tier), rs in sorted(groups.items()):
        b = bound_of(alg, group, tier, rs, session, resamples, seed)
        if b is None:
            skipped[f"{alg} {group} {tier}: no verified run, nothing to fit"] += len(rs)
            continue
        bounds.append(b)
    return bounds, skipped


# ── Listing ────────────────────────────────────────────────────────


def _fmt(v: float | None, digits: int = 3) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def _fmt_ci(ci: Sequence[float] | None) -> str:
    return "-" if not ci else f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def describe(name: str, doc: dict[str, Any]) -> str:
    dom = doc["domain"]
    fit = doc["fit"]
    ops = doc["dimensions"]["ops"]
    memv = doc["dimensions"]["memory"]
    return (
        f"{name:<28} {doc['bound_id']}  {dom['family']:<8} {dom['tier']:<6} {doc['level']:<8} "
        f"sizes={fit['sizes']} runs={doc['provenance']['verified']}/{doc['provenance']['records']} "
        f"alpha={_fmt(fit['alpha'])} {_fmt_ci(fit['alpha_ci95'])} "
        f"ops={_fmt(ops['value'])} {_fmt_ci(ops['ci95'])} "
        f"S={_fmt(doc['constant']['s']['value'])} "
        f"mem/sqrt r={_fmt(memv['value'], 4)} {doc['admissibility']['status']}"
    )


def cmd_emit(args: argparse.Namespace) -> int:
    sweep = Path(args.sweep)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    header, rows = read_sweep(sweep)
    bounds, skipped = build_bounds(header, rows, sweep, root, args.resamples, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for b in bounds:
        (out / b.name).write_text(b.text, encoding="utf-8")
        print(describe(b.name, b.doc))
    for why, count in sorted(skipped.items()):
        print(f"skipped {count} rows: {why}", file=sys.stderr)
    print(f"{len(bounds)} record(s) written to {out}", file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        files.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    bad = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        try:
            check_seal(text, "bound_id", BOUND_PREFIX)
            doc = json.loads(text)
            if doc.get("schema") != SCHEMA:
                raise ValueError(f"schema {doc.get('schema')!r}")
            if domain_id(doc["domain"]) != doc["domain_id"]:
                raise ValueError("domain_id does not hash the domain")
        except ValueError as e:
            print(f"{f}: {e}")
            bad += 1
            continue
        print(describe(f.name, doc))
    return 1 if bad else 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    em = sub.add_parser("emit", help="write one record per (algorithm, group kind, tier)")
    em.add_argument("--sweep", required=True, help="the `ca_bench ... --json FILE` output")
    em.add_argument("--out", default=str(Path(__file__).resolve().parent / "records"))
    em.add_argument(
        "--root", default=None, help="repository root the session dir is written relative to"
    )
    em.add_argument("--resamples", type=int, default=RESAMPLES)
    em.add_argument("--seed", type=int, default=SEED)
    em.set_defaults(func=cmd_emit)
    ls = sub.add_parser("list", help="check seals and domain ids, print one line per record")
    ls.add_argument("paths", nargs="+")
    ls.set_defaults(func=cmd_list)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
