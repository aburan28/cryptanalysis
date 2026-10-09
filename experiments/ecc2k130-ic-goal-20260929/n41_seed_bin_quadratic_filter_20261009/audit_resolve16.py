#!/usr/bin/env python3
"""Independent installed-Sage replay of the exact N41 public-Q relation."""

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


def features(x: int) -> int:
    if x & 1 or x >> 41:
        raise ValueError("x outside frozen coordinate encoding")
    result = 1
    active = []
    for bit in range(1, 41):
        if x & (1 << bit):
            result |= 1 << bit
            active.append(bit - 1)
    for k, left in enumerate(active):
        for right in active[k + 1:]:
            result |= 1 << (41 + left * (79 - left) // 2 + right - left - 1)
    return result


def equations_for(filters: bytes, left_seed: int, right_seed: int):
    bin_index = (left_seed - 1) * 63 + right_seed - 1
    offset = bin_index * (4 + 16 * 104)
    rank, count, reserved = struct.unpack_from("<HBB", filters, offset)
    if rank > 821 or count > 16 or reserved:
        raise ValueError("invalid selected filter bin")
    return [int.from_bytes(filters[offset + 4 + 104 * k:
                                   offset + 4 + 104 * (k + 1)], "little")
            for k in range(count)]


def main() -> None:
    output = HERE / "resolve16_audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent resolver audit")
    start = time.monotonic_ns()
    frozen = json.loads((HERE / "resolve16_audit_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"audit input changed: {name}")
    if sha(Path(__file__)) != frozen["audit_source_sha256"]:
        raise ValueError("audit source changed")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "resolve16_result.json").read_text())
    if sha(Path(frozen["prior_census_path"])) != frozen["prior_census_sha256"]:
        raise ValueError("prior exact census changed")
    for name, expected in protocol["input_sha256"].items():
        if sha(Path(protocol["inputs"][name])) != expected:
            raise ValueError(f"frozen geometry or arithmetic changed: {name}")
    prior = json.loads(Path(frozen["prior_census_path"]).read_text())
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    if (result["status"] != "FOUND_VERIFIED_RELATION" or
            result["rows_verified"] != 1 or
            result["witness_pair_state_indices"] != prior["saved_witnesses"][0]["pair_state_indices"] or
            result["public_target_q"] != geometry["public_target_q"]):
        raise ValueError("reported relation differs from independently audited census")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(value >> bit) & 1 for bit in range(41)]))

    def encode(value):
        return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))

    source_rows = [geometry["point_rows_by_unique_rotation"][str(rotation)]
                   for rotation in (0, 10, 20, 30)]
    point_rows = [[curve(decode(row[0]), decode(row[1])) for row in rows]
                  for rows in source_rows]
    order = int(protocol["subgroup_order"])
    if any(order * point != curve(0) for domain in point_rows for point in domain):
        raise ValueError("source point outside subgroup")
    domains = []
    for rows, points in zip(source_rows, point_rows):
        pairs = []
        for i in range(64):
            for j in range(i + 1, 64):
                if rows[i][2] == rows[j][2]:
                    continue
                pairs.append((points[i] + points[j],
                              (1 << rows[i][2]) | (1 << rows[j][2]),
                              rows[i][3] ^ rows[j][3], i, j))
        if len(pairs) != 1956:
            raise ValueError("Sage pair-domain size changed")
        domains.append(pairs)
    q = curve(decode(result["public_target_q"][0]),
              decode(result["public_target_q"][1]))
    if order * q != curve(0):
        raise ValueError("public Q failed subgroup check")
    indices = result["witness_pair_state_indices"]
    states = [domains[k][index] for k, index in enumerate(indices)]
    selected_columns = [source_rows[k][position][2] for k, state in enumerate(states)
                        for position in state[3:5]]
    if (len(set(selected_columns)) != 8 or
            sum((state[0] for state in states), curve(0)) != q):
        raise ValueError("Sage eight-point relation or folded-column rule failed")
    residual = q - states[0][0] - states[1][0]
    if (residual != states[2][0] + states[3][0] or
            encode(residual[0]) != result["witness_residual_x"]):
        raise ValueError("Sage target residual differs")
    visited = indices[0] * 1956 + indices[1] + 1
    if visited != result["visited_prefixes"]:
        raise ValueError("prefix visitation order differs")
    valid = 0
    for i in range(indices[0] + 1):
        end = indices[1] + 1 if i == indices[0] else 1956
        valid += sum(not (domains[0][i][1] & domains[1][j][1]) for j in range(end))
    if valid != result["valid_prefixes"]:
        raise ValueError("valid-prefix ordinal differs")
    filters = (HERE / "filters16.bin").read_bytes()
    if len(filters) != 3969 * (4 + 16 * 104):
        raise ValueError("filter table length changed")
    witness_equations = equations_for(filters, states[2][2], states[3][2])
    if any((features(result["witness_residual_x"]) & eq).bit_count() & 1
           for eq in witness_equations):
        raise ValueError("genuine witness rejected by selected filter equations")
    sampled_orbits = 0
    with (HERE / "x_orbits.bin").open("rb") as stream:
        for sample in range(128):
            index = (sample * (1583568 - 1)) // 127
            stream.seek(index * 12)
            raw = stream.read(12)
            left_seed, right_seed = raw[0], raw[1]
            x = int.from_bytes(raw[2:8], "little")
            left_id, right_id = struct.unpack_from("<HH", raw, 8)
            left, right = domains[2][left_id], domains[3][right_id]
            pair_sum = left[0] + right[0]
            if (left[1] & right[1] or left[2] != left_seed or
                    right[2] != right_seed or pair_sum == curve(0) or
                    encode(pair_sum[0]) != x or
                    any((features(x) & eq).bit_count() & 1
                        for eq in equations_for(filters, left_seed, right_seed))):
                raise ValueError("sampled exact suffix orbit or filter failed Sage replay")
            sampled_orbits += 1
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if (time.monotonic_ns() - start > frozen["wall_cap_seconds"] * 10**9 or
            peak > frozen["rss_cap_bytes"]):
        raise ValueError("independent audit exceeded resource cap")
    audit = {
        "status": "PASS_INDEPENDENT_SAGE_ORDINARY_RELATION_REPLAY",
        "curve_id": result["curve_id"], "public_target_q": result["public_target_q"],
        "checked_source_points": 256, "checked_pair_states": 7824,
        "checked_first_valid_prefix_ordinal": valid,
        "witness_pair_state_indices": indices,
        "witness_point_indices": [[state[3], state[4]] for state in states],
        "witness_folded_columns": selected_columns,
        "witness_filter_equations_checked": len(witness_equations),
        "sampled_exact_suffix_orbits_checked": sampled_orbits,
        "wall_ns": time.monotonic_ns() - start, "peak_rss_bytes": peak,
        "audit_protocol_sha256": sha(HERE / "resolve16_audit_protocol.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage-runtime-info.json"),
    }
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
