#!/usr/bin/env python3
"""Freeze the exact n53 weight-three x supports that fail curve lifting."""

import base64
import gzip
import hashlib
import itertools
import json
import time
from pathlib import Path

from run_probe import HERE, curve_record, curves, field, sha


def main():
    output = HERE / "bases/n53_weight3_nonrational_supports.json.gz"
    assert not output.exists()
    manifest_path, candidate = curve_record(53)
    assert candidate["curve"]["curve_id"] == "EC1N53Ckb1hf77aab617904"
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    invalid = []
    valid = 0
    started = time.perf_counter()
    for weight in (1, 2, 3):
        for support in itertools.combinations(range(53), weight):
            mask = sum(1 << index for index in support)
            point = curve.pointFromX(onb.fromCoords(mask))
            if point is None:
                invalid.append(mask)
            else:
                assert curve.mul(point, 428) is not None
                valid += 1
    assert valid == 12031
    assert len(invalid) == 24857 - valid
    packed = b"".join(mask.to_bytes(7, "little") for mask in invalid)
    receipt = {
        "kind": "n53_exact_nonrational_normal_weight3_x_supports",
        "proposal_id": "Q1308",
        "candidate_id": None,
        "curve_id": candidate["curve"]["curve_id"],
        "isogeny": "none",
        "normal_basis_weight_bound": 3,
        "nominal_nonzero_x_masks": valid + len(invalid),
        "rational_x_masks": valid,
        "nonrational_x_masks": len(invalid),
        "encoding": "ordered nonrational support masks, 7-byte little-endian",
        "nonrational_supports_sha256": hashlib.sha256(packed).hexdigest(),
        "nonrational_supports_base64": base64.b64encode(packed).decode("ascii"),
        "elapsed_seconds": time.perf_counter() - started,
        "curve_manifest_sha256": sha(manifest_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
    }
    content = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    with output.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as compressed:
            compressed.write(content)
    print(json.dumps({"valid": valid, "invalid": len(invalid),
                      "support_sha256": receipt["nonrational_supports_sha256"],
                      "elapsed_seconds": receipt["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
