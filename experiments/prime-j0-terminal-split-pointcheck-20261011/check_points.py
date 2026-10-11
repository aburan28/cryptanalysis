#!/usr/bin/env python3
"""Replay frozen radix paths as secp256k1 group operations."""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / "prime-j0-terminal-split-20261011"
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
LAMBDA = (-V[0] * pow(V[1], -1, N)) % N
RADIX = 1024


def digest(raw):
    return sha256(raw).hexdigest()


def negate(point):
    return None if point is None else (point[0], (-point[1]) % P)


def add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if x1 == x2:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, P)
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P, -1, P)
    slope %= P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(scalar, point):
    if scalar < 0:
        return multiply(-scalar, negate(point))
    result = None
    while scalar:
        if scalar & 1:
            result = add(result, point)
        scalar >>= 1
        if scalar:
            point = add(point, point)
    return result


PHI_G = multiply(LAMBDA, G)


@lru_cache(maxsize=65536)
def pair_point(a, b):
    return add(multiply(a, G), multiply(b, PHI_G))


def path_point(option):
    path = option["path"]
    result = None
    for a, b in option["terminal_parts"]:
        result = add(result, pair_point(int(a), int(b)))
    for a, b, *_ in reversed(path["digits"]):
        result = add(multiply(RADIX, result), pair_point(int(a), int(b)))
    return result


def main():
    input_raw = (PANEL / "holdout-inputs.json").read_bytes()
    path_raw = (PANEL / "holdout-paths.jsonl").read_bytes()
    screen_raw = (PANEL / "holdout-screen.json").read_bytes()
    algebra_raw = (PANEL / "holdout-check.json").read_bytes()
    inputs = json.loads(input_raw)
    screen = json.loads(screen_raw)
    algebra = json.loads(algebra_raw)
    assert screen["input_sha256"] == digest(input_raw)
    assert screen["certificate_sha256"] == algebra["certificate_sha256"] == digest(path_raw)
    assert algebra["status"] == "passed" and screen["status"] == "screened"
    assert (G[1] * G[1] - G[0] * G[0] * G[0] - 7) % P == 0
    assert multiply(N, G) is None
    assert (LAMBDA * LAMBDA - 3 * LAMBDA + 3) % N == 0
    records = [json.loads(line) for line in path_raw.splitlines()]
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(records) == len(scalars) == 4096
    indices = list(range(128))
    split_extra = [i for i, record in enumerate(records) if i >= 128 and
                   len(record["options"][record["selected_option"]]["terminal_parts"]) == 2][:128]
    assert len(split_extra) == 128
    indices += split_extra
    point_stream = sha256()
    split_checked = 0
    changed_checked = 0
    for index in indices:
        record = records[index]
        assert record["index"] == index and record["baseline_option"] == 0
        scalar = scalars[index] % N
        expected = multiply(scalar, G)
        assert expected is not None
        baseline = record["options"][0]
        selected = record["options"][record["selected_option"]]
        assert path_point(baseline) == expected, (index, "baseline")
        assert path_point(selected) == expected, (index, "selected")
        split_checked += len(selected["terminal_parts"]) == 2
        changed_checked += record["selected_option"] != 0
        point_stream.update(index.to_bytes(4, "big"))
        for coordinate in expected:
            point_stream.update(coordinate.to_bytes(32, "big"))
    result = {
        "schema": 1,
        "status": "passed",
        "input_sha256": digest(input_raw),
        "certificate_sha256": digest(path_raw),
        "algebra_check_sha256": digest(algebra_raw),
        "verifier_sha256": digest(Path(__file__).read_bytes()),
        "checked_cases": len(indices),
        "checked_split_cases": split_checked,
        "checked_changed_cases": changed_checked,
        "indices": indices,
        "point_stream_sha256": point_stream.hexdigest(),
    }
    output = HERE / "point-check.json"
    if output.exists():
        raise SystemExit("refusing to overwrite point-path receipt")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "checked_cases", "checked_split_cases",
                       "checked_changed_cases", "point_stream_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
