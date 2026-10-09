#!/usr/bin/env python3
"""Independent Sage replay of the frozen public-Q quadratic-filter panel."""

import hashlib
import json
import resource
import struct
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_bits(x: int) -> int:
    if x & 1 or x >> 41:
        raise ValueError("x outside coordinate encoding")
    bits = 1
    active = []
    for bit in range(1, 41):
        if x & (1 << bit):
            bits |= 1 << bit
            active.append(bit - 1)
    for a, left in enumerate(active):
        for right in active[a + 1:]:
            bits |= 1 << (41 + left * (79 - left) // 2 + right - left - 1)
    return bits


def main() -> None:
    output = HERE / "query_audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent query audit")
    start = time.monotonic_ns()
    frozen = json.loads((HERE / "audit_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"audit input changed: {name}")
    if sha(Path(__file__)) != frozen["audit_source_sha256"]:
        raise ValueError("audit source changed")
    protocol = json.loads((HERE / "protocol.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    if query["status"] != "COMPLETE_PANEL" or query["valid_prefixes"] != 8192:
        raise ValueError("query panel status changed")
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(value >> bit) & 1 for bit in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    target = curve(decode(protocol["public_target_q"][0]),
                   decode(protocol["public_target_q"][1]))
    if int(protocol["subgroup_order"]) * target != curve(0):
        raise ValueError("public Q failed subgroup replay")
    domains = []
    for rotation in (0, 10, 20, 30):
        source = geometry["point_rows_by_unique_rotation"][str(rotation)]
        points = [curve(decode(row[0]), decode(row[1])) for row in source]
        if len(points) != 64 or any(int(protocol["subgroup_order"]) * p != curve(0)
                                     for p in points):
            raise ValueError("source point or subgroup replay failed")
        pairs = []
        for i in range(64):
            for j in range(i + 1, 64):
                if source[i][2] == source[j][2]:
                    continue
                pairs.append((points[i] + points[j],
                              (1 << source[i][2]) | (1 << source[j][2]),
                              source[i][3] ^ source[j][3]))
        if len(pairs) != 1956:
            raise ValueError("Sage pair-domain size changed")
        domains.append(pairs)
    data = (HERE / "residuals.bin").read_bytes()
    if len(data) != 8192 * 10:
        raise ValueError("query residual record count changed")
    x_values = set()
    with (HERE / "x_orbits.bin").open("rb") as orbit_file:
        for _ in range(1583568):
            row = orbit_file.read(12)
            if len(row) != 12:
                raise ValueError("truncated exact suffix orbit")
            x_values.add(int.from_bytes(row[2:8], "little"))
        if orbit_file.read(1):
            raise ValueError("trailing exact suffix orbit")
    if len(x_values) != 1583568:
        raise ValueError("exact suffix x support is not unique")
    filters = (HERE / "filters.bin").read_bytes()
    if len(filters) != 3969 * (4 + 8 * 13 * 8):
        raise ValueError("filter table size changed")
    equations = []
    transpose = [[0] * 8 for _ in range(821)]
    for bin_index in range(3969):
        offset = bin_index * (4 + 8 * 13 * 8)
        rank, count, reserved = struct.unpack_from("<HBB", filters, offset)
        if rank > 821 or reserved or count > 8:
            raise ValueError("invalid filter bin")
        active_equations = []
        for eq in range(count):
            coefficients = int.from_bytes(filters[offset + 4 + 104 * eq:
                                                  offset + 4 + 104 * (eq + 1)], "little")
            if coefficients >> 821:
                raise ValueError("filter coefficient outside family")
            active_equations.append(coefficients)
            remaining = coefficients
            while remaining:
                low = remaining & -remaining
                feature = low.bit_length() - 1
                transpose[feature][eq] |= 1 << bin_index
                remaining ^= low
        equations.append(active_equations)
    exact_hits = 0
    independently_screened = 64
    screened_passed = 0
    all_bins_mask = (1 << 3969) - 1
    pass_counts = []
    for index in range(8192):
        x = int.from_bytes(data[10 * index:10 * index + 6], "little")
        left_index, right_index = struct.unpack_from("<HH", data, 10 * index + 6)
        if (left_index >= 1956 or right_index >= 1956 or
                domains[0][left_index][1] & domains[1][right_index][1]):
            raise ValueError("query prefix index or column rule failed")
        residual = target - domains[0][left_index][0] - domains[1][right_index][0]
        if residual == curve(0) or encode(residual[0]) != x:
            raise ValueError("Sage residual x replay failed")
        exact_hits += x in x_values
        features = feature_bits(x)
        parities = [0] * 8
        remaining = features
        while remaining:
            low = remaining & -remaining
            feature = low.bit_length() - 1
            rows = transpose[feature]
            for eq in range(8):
                parities[eq] ^= rows[eq]
            remaining ^= low
        failed = 0
        for parity in parities:
            failed |= parity
        passed = 3969 - (failed & all_bins_mask).bit_count()
        pass_counts.append(passed)
        if index < independently_screened:
            direct = sum(all((features & eq).bit_count() % 2 == 0
                             for eq in bin_equations)
                         for bin_equations in equations)
            if direct != passed:
                raise ValueError("independent direct and transposed filter counts differ")
            screened_passed += direct
        if time.monotonic_ns() - start > frozen["wall_cap_seconds"] * 10**9:
            raise TimeoutError("independent audit wall cap")
    sorted_counts = sorted(pass_counts)
    if (sum(pass_counts) != query["total_seed_bins_passed"] or
            sorted_counts[0] != query["minimum_seed_bins_passed"] or
            sorted_counts[len(sorted_counts) // 2] != query["median_seed_bins_passed"] or
            sorted_counts[-1] != query["maximum_seed_bins_passed"]):
        raise ValueError("independent quadratic-bin screen disagrees with native query")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if peak > frozen["rss_cap_bytes"]:
        raise MemoryError("independent audit RSS cap")
    result = {
        "status": "PASS_INDEPENDENT_SAGE_PUBLIC_RESIDUAL_REPLAY",
        "curve_id": frozen["curve_id"], "public_target_q": protocol["public_target_q"],
        "checked_source_points": 256,
        "checked_prefix_pair_states": 3912,
        "checked_public_residuals": 8192,
        "exact_suffix_x_support_size": len(x_values),
        "exact_x_hits_in_panel": exact_hits,
        "independently_screened_residuals": independently_screened,
        "independently_screened_bin_passes": screened_passed,
        "independently_screened_full_panel_bin_passes": sum(pass_counts),
        "independently_screened_median_bin_passes": sorted_counts[len(sorted_counts) // 2],
        "query_reported_total_bin_passes": query["total_seed_bins_passed"],
        "wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": peak,
        "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
        "query_protocol_sha256": sha(HERE / "query_protocol_v3.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage-runtime-info.json"),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
