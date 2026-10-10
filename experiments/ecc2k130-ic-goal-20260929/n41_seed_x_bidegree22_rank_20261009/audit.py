#!/usr/bin/env python3
"""Independent Sage and Python replay of the bidegree-rank input and features."""

import hashlib
import json
import resource
import struct
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "../n41_seed_bin_quadratic_filter_20261009"
MASK64 = (1 << 64) - 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active(value: int, bits: int):
    chosen = [i for i in range(bits) if (value >> i) & 1]
    output = [0] + [i + 1 for i in chosen]
    for a, left in enumerate(chosen):
        for right in chosen[a + 1:]:
            output.append(1 + bits + left * (2 * bits - left - 1) // 2 +
                          right - left - 1)
    return output


def main() -> None:
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent bidegree-rank audit")
    start = time.monotonic_ns()
    frozen = json.loads((HERE / "audit_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"rank-audit input changed: {name}")
    if sha(Path(__file__)) != frozen["audit_source_sha256"]:
        raise ValueError("rank-audit source changed")
    prior_protocol = json.loads((SOURCE / "protocol.json").read_text())
    if sha(SOURCE / "x_orbits.bin") != frozen["source_x_orbits_sha256"]:
        raise ValueError("prior exact orbit input changed")
    geometry_path = Path(prior_protocol["inputs"]["geometry"])
    if (sha(geometry_path) != prior_protocol["input_sha256"]["geometry"] or
            sha(geometry_path) != frozen["source_geometry_sha256"]):
        raise ValueError("source geometry changed")
    geometry = json.loads(geometry_path.read_text())["n41"]
    sample = (HERE / "sample.bin").read_bytes()
    index_bytes = (HERE / "sample_indices.bin").read_bytes()
    exact = (SOURCE / "x_orbits.bin").read_bytes()
    if len(sample) != 80000 * 8 or len(index_bytes) != 80000 * 4:
        raise ValueError("frozen sample length changed")
    indices = list(struct.unpack("<80000I", index_bytes))
    if indices != sorted(set(indices)) or indices[-1] >= 1583568:
        raise ValueError("sample indices are not unique and ordered")
    digest = 1469598103934665603
    total_active = 0
    bins = set()
    for row, index in enumerate(indices):
        raw = exact[index * 12:(index + 1) * 12]
        current = sample[row * 8:(row + 1) * 8]
        if current != raw[:8]:
            raise ValueError("sample does not match exact sign-orbit source")
        s, t = current[:2]
        x = int.from_bytes(current[2:8], "little")
        bins.add((s, t))
        if row < 256:
            seed_features = active(s | (t << 6), 12)
            x_features = active(x >> 1, 40)
            total_active += len(seed_features) * len(x_features)
            for left in seed_features:
                for right in x_features:
                    digest ^= left * 821 + right + 1
                    digest = (digest * 1099511628211) & MASK64
    if len(bins) != 3969:
        raise ValueError("all seed bins not represented by frozen sample")
    rank = json.loads((HERE / "rank_result.json").read_text())
    control = json.loads((HERE / "rank_control.json").read_text())
    if (control["status"] != "EXIT_SUCCESS" or
            control["rank_result_sha256"] != sha(HERE / "rank_result.json") or
            rank["first_256_feature_digest_fnv64"] != digest or
            rank["rows"] != 80000 or rank["tensor_features"] != 64859):
        raise ValueError("rank source or independent feature digest differs")
    ring = PolynomialRing(GF(2), "t")
    symbol = ring.gen()
    field = GF(2**41, "t", modulus=symbol**41 + symbol**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(value >> bit) & 1 for bit in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    domains = []
    for rotation in (20, 30):
        source = geometry["point_rows_by_unique_rotation"][str(rotation)]
        points = [curve(decode(row[0]), decode(row[1])) for row in source]
        if any(int(geometry["subgroup_order"]) * point != curve(0)
               for point in points):
            raise ValueError("source point failed subgroup check")
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
    checked_orbits = 0
    for k in range(64):
        row = (k * 79999) // 63
        index = indices[row]
        raw = exact[index * 12:(index + 1) * 12]
        s, t = raw[0], raw[1]
        x = int.from_bytes(raw[2:8], "little")
        left_index, right_index = struct.unpack_from("<HH", raw, 8)
        left, right = domains[0][left_index], domains[1][right_index]
        total = left[0] + right[0]
        if (left[1] & right[1] or left[2] != s or right[2] != t or
                total == curve(0) or encode(total[0]) != x):
            raise ValueError("Sage sampled exact suffix sum replay failed")
        checked_orbits += 1
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if (time.monotonic_ns() - start > frozen["wall_cap_seconds"] * 10**9 or
            peak > frozen["rss_cap_bytes"]):
        raise ValueError("independent audit resource cap")
    audit = {
        "status": "PASS_INDEPENDENT_BIDEGREE_INPUT_FEATURE_AND_SAGE_REPLAY",
        "curve_id": frozen["curve_id"],
        "checked_sample_rows": 80000, "checked_seed_bins": len(bins),
        "checked_source_points": 128,
        "checked_suffix_pair_states": 3912,
        "sage_replayed_sample_orbits": checked_orbits,
        "first_256_feature_digest_fnv64": digest,
        "first_256_active_feature_count": total_active,
        "rank": rank["rank"], "tensor_features": rank["tensor_features"],
        "wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": peak,
        "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage-runtime-info.json"),
    }
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
