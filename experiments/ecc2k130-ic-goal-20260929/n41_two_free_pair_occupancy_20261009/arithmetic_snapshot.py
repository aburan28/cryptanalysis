#!/usr/bin/env python3
"""Independent arithmetic replay of compact-orbit slope-panel relations.

Pure-Python GF(2^n) and Koblitz arithmetic; shares no code with the Rust
producer. For every panel record it checks, from the retained base header and
the published rho fixture only:

  * target == [published scalar] G and has prime order r,
  * every reported x-code is a factor-base x-coordinate,
  * some sign choice of the four base points sums to the target,
  * the pinned intermediates are x(P0 +/- P1) and x(P2 +/- P3),
  * each used base point lies on the curve and has order r.
"""

import itertools
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PANEL = ROOT / "research/sat_factor_base_review_20260908/autolab_shared_log_scaling_20260912/runs"


class Field:
    def __init__(self, n, low_terms):
        self.n = n
        self.modulus = (1 << n) | sum(1 << t for t in low_terms)

    def mul(self, a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if (a >> self.n) & 1:
                a ^= self.modulus
        return result

    def inv(self, a):
        assert a
        r0, r1, s0, s1 = self.modulus, a, 0, 1
        while r1 != 1:
            shift = r0.bit_length() - r1.bit_length()
            if shift < 0:
                r0, r1, s0, s1 = r1, r0, s1, s0
                continue
            r0 ^= r1 << shift
            s0 ^= s1 << shift
            if r0.bit_length() < r1.bit_length():
                r0, r1, s0, s1 = r1, r0, s1, s0
        return s1


class Curve:
    """y^2 + xy = x^3 + a x^2 + 1 over GF(2^n); None is the point at infinity."""

    def __init__(self, field, a):
        self.f, self.a = field, a

    def on_curve(self, p):
        if p is None:
            return True
        x, y = p
        f = self.f
        lhs = f.mul(y, y) ^ f.mul(x, y)
        x2 = f.mul(x, x)
        rhs = f.mul(x2, x) ^ (x2 if self.a else 0) ^ 1
        return lhs == rhs

    def neg(self, p):
        return None if p is None else (p[0], p[0] ^ p[1])

    def add(self, p, q):
        if p is None:
            return q
        if q is None:
            return p
        f = self.f
        x1, y1 = p
        x2, y2 = q
        if x1 == x2:
            if x1 == 0 or y2 == (y1 ^ x1):
                return None
            lam = x1 ^ f.mul(y1, f.inv(x1))
            x3 = f.mul(lam, lam) ^ lam ^ (1 if self.a else 0)
            y3 = f.mul(x1, x1) ^ f.mul(lam ^ 1, x3)
            return (x3, y3)
        lam = f.mul(y1 ^ y2, f.inv(x1 ^ x2))
        x3 = f.mul(lam, lam) ^ lam ^ x1 ^ x2 ^ (1 if self.a else 0)
        y3 = f.mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)

    def mul(self, k, p):
        result, base = None, p
        while k:
            if k & 1:
                result = self.add(result, base)
            base = self.add(base, base)
            k >>= 1
        return result


def points_with_x(curve, x):
    """Solve y^2 + xy = x^3 + a x^2 + 1 for y (0, 1, or 2 points)."""
    f = curve.f
    rhs = f.mul(f.mul(x, x), x) ^ (f.mul(x, x) if curve.a else 0) ^ 1
    if x == 0:
        # y^2 = rhs -> unique square root y = rhs^(2^(n-1)).
        y = rhs
        for _ in range(f.n - 1):
            y = f.mul(y, y)
        return [(0, y)]
    # Substitute y = x*z: z^2 + z = rhs / x^2. Solvable iff trace == 0.
    c = f.mul(rhs, f.inv(f.mul(x, x)))
    if trace(f, c) != 0:
        return []
    z = half_trace(f, c)
    return [(x, f.mul(x, z)), (x, f.mul(x, z ^ 1))]


def trace(f, a):
    t = a
    acc = a
    for _ in range(f.n - 1):
        t = f.mul(t, t)
        acc ^= t
    return acc & 1


def half_trace(f, a):
    # For odd n, H(a) = sum_{i=0}^{(n-1)/2} a^(2^(2i)) solves z^2 + z = a.
    assert f.n % 2 == 1
    h = 0
    term = a
    for _ in range((f.n - 1) // 2 + 1):
        h ^= term
        term = square(f, square(f, term))
    return h


def square(f, a):
    return f.mul(a, a)


def load_header(block_dir):
    override = os.environ.get("REPLAY_BASE")
    path = Path(override) if override else block_dir / "direct/stdout.txt"
    return json.loads(path.open("rb").readline())


def factor_r(order):
    r, d = order, 2
    factors = {}
    while d * d <= r:
        while r % d == 0:
            factors[d] = factors.get(d, 0) + 1
            r //= d
        d += 1
    if r > 1:
        factors[r] = factors.get(r, 0) + 1
    return factors


def replay_record(rec, header, curve, r, x_codes, base_points_by_x):
    checks = {}
    f = curve.f
    gen = tuple(rec["generator"])
    target = tuple(rec["target"])
    checks["generator_on_curve"] = curve.on_curve(gen)
    checks["target_on_curve"] = curve.on_curve(target)
    checks["target_is_scalar_times_g"] = curve.mul(rec["published_fixture_scalar"], gen) == target
    checks["target_matches_published_q"] = target == tuple(rec["published_q"])
    checks["generator_has_order_r"] = curve.mul(r, gen) is None
    codes = rec["x_codes"]
    checks["all_x_codes_in_base"] = all(code in x_codes for code in codes)
    # Enumerate the sign choices of the four base points.
    point_options = []
    ok_points = True
    for code in codes:
        pts = base_points_by_x.get(code)
        if not pts:
            ok_points = False
            break
        point_options.append(pts)
    checks["x_codes_have_base_points"] = ok_points
    relation_found = False
    intermediates_ok = False
    if ok_points:
        want_u, want_v = rec["pinned_intermediates"]
        for choice in itertools.product(*point_options):
            s = None
            for p in choice:
                s = curve.add(s, p)
            if s == target:
                relation_found = True
                u = curve.add(choice[0], choice[1])
                v = curve.add(choice[2], choice[3])
                ux = u[0] if u else None
                vx = v[0] if v else None
                if {ux, vx} == {want_u, want_v} or (ux == want_u and vx == want_v):
                    intermediates_ok = True
                    break
        checks["group_relation_sums_to_target"] = relation_found
        checks["pinned_intermediates_match"] = intermediates_ok
        checks["base_points_have_order_r"] = all(
            curve.mul(r, p) is None for options in point_options for p in options
        )
    if rec.get("recovered_scalar") is not None:
        checks["recovered_log_times_g_is_target"] = curve.mul(rec["recovered_scalar"], gen) == target
        checks["recovered_log_matches_published"] = rec["recovered_scalar"] == rec["published_fixture_scalar"] % r
    return checks


def main():
    arguments = sys.argv[1:]
    records_dir, pattern, report = HERE / "slope_panel", "n{n}_block{b:02d}.jsonl", HERE / "independent_replay.json"
    if arguments and arguments[0] == "--dlp":
        records_dir, pattern, report = Path(arguments[1]), "dlp_n{n}_b{b}.jsonl", Path(arguments[2])
        arguments = arguments[3:]
    fields = [int(v) for v in (arguments or ["37", "41", "53"])]
    summary = {"records_dir": str(records_dir), "fields": {}, "all_pass": True, "total_records": 0}
    for n in fields:
        panel_field = {"blocks": 0, "records": 0, "pass": 0, "fail": 0, "failures": []}
        record_paths = (
            sorted(records_dir.glob(f"dlp_n{n}_b*.jsonl"))
            or sorted(records_dir.glob(f"ic_n{n}_b*.jsonl"))
            or sorted(records_dir.glob(f"n{n}_block*.jsonl"))
        )
        if not record_paths:
            record_paths = [
                records_dir / pattern.format(n=n, b=int(block_dir.name.split("_")[1]))
                for block_dir in sorted((PANEL / f"n{n}").glob("block_*"))
            ]
        for record_path in record_paths:
            if not record_path.exists():
                continue
            header_source = PANEL / f"n{n}" / "block_00"
            header = load_header(header_source if header_source.exists() else Path("."))
            f = Field(n, header["field_modulus_low_terms"])
            curve = Curve(f, header["a"])
            r = header["subgroup_order"]
            x_codes = set(header.get("factor_base_x_codes") or [])
            base_points_by_x = {}
            for raw in header["factor_base_point_coordinates"]:
                if raw is None:
                    continue
                x, y = raw
                base_points_by_x.setdefault(x, []).append((x, y))
                x_codes.add(x)
            panel_field["blocks"] += 1
            for line in record_path.read_text().splitlines():
                rec = json.loads(line)
                if rec.get("exit_code") != 0 or not rec.get("x_codes"):
                    continue
                panel_field["records"] += 1
                summary["total_records"] += 1
                checks = replay_record(rec, header, curve, r, x_codes, base_points_by_x)
                if all(checks.values()):
                    panel_field["pass"] += 1
                else:
                    panel_field["fail"] += 1
                    panel_field["failures"].append(
                        {"block": rec.get("block", record_path.name), "fixture_index": rec["fixture_index"],
                         "failed": [k for k, v in checks.items() if not v]}
                    )
                    summary["all_pass"] = False
            print(f"n={n} file={record_path.name} cumulative pass={panel_field['pass']} fail={panel_field['fail']}", flush=True)
        summary["fields"][str(n)] = panel_field
    if summary["total_records"] == 0:
        summary["all_pass"] = False
        summary["error"] = "no records replayed"
    report.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: {"pass": v["pass"], "fail": v["fail"]} for k, v in summary["fields"].items()}, indent=2))
    print("all_pass", summary["all_pass"])
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
