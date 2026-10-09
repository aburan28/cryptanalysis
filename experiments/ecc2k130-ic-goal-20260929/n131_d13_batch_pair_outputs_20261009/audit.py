#!/usr/bin/env sage -python
"""Independent scalar and source-curve replay of saved pair-output samples."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pilot


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    result = json.loads(pilot.RESULT.read_text())
    protocol = json.loads(pilot.PROTOCOL.read_text())
    if result["status"] != "PASS" or result["protocol_sha256"] != sha(pilot.PROTOCOL):
        raise ValueError("pilot result does not match frozen protocol")
    (frozen, onb, raw_curve, curve, valid, points, raw_points,
     to_pb, sage_int) = pilot.setup()
    assert frozen == protocol and len(valid) == 4134
    expected_pairs = sum(len(valid) - i - 1 for i in range(protocol["left_count"]))
    assert result["unordered_pairs"] == expected_pairs == 262496
    assert result["signed_x_outputs"] == 2 * expected_pairs
    assert result["distinct_output_x"] <= result["signed_x_outputs"]
    assert result["full_domain_unordered_pairs"] == len(valid) * (len(valid)-1) // 2
    assert result["full_domain_signed_outputs_upper"] == len(valid) * (len(valid)-1)
    assert result["full_domain_raw_payload_bytes_upper"] == (
        result["full_domain_signed_outputs_upper"] * protocol["record_bytes"])
    assert result["setup_ns"] + result["batch_add_ns"] + result["encode_ns"] <= result["elapsed_ns"]
    assert result["elapsed_ns"] <= protocol["wall_cap_seconds"] * 10**9
    assert result["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
    assert len(result["samples"]) == 96

    index = {code: i for i, code in enumerate(valid)}
    checked = []
    for item in result["samples"]:
        a = index[item["left_code"]]
        b = index[item["right_code"]]
        branch = item["branch"]
        assert 0 <= a < protocol["left_count"] and a < b
        assert branch in (0, 1)
        source_right = raw_points[b] if branch == 0 else raw_curve.neg(raw_points[b])
        source_sum = raw_curve.add(raw_points[a], source_right)
        assert source_sum is not None
        source_x = to_pb(source_sum[0])
        sage_right = points[b] if branch == 0 else -points[b]
        scalar_sum = points[a] + sage_right
        scalar_x = sage_int(scalar_sum[0])
        assert source_x == scalar_x == item["x_pb"]
        checked.append((a, b, branch))

    receipt = {"kind": "n131_d13_batch_pair_output_independent_audit",
               "status": "PASS", "curve_id": protocol["curve_id"],
               "sample_outputs_replayed": len(checked),
               "independent_paths": ["source ONB curve addition",
                                     "installed Sage scalar curve addition"],
               "pilot_unordered_pairs": result["unordered_pairs"],
               "pilot_signed_x_outputs": result["signed_x_outputs"],
               "full_domain_raw_payload_bytes_upper":
                   result["full_domain_raw_payload_bytes_upper"],
               "source_sha256": {"audit": sha(__file__),
                                 "pilot_result": sha(pilot.RESULT),
                                 "protocol": sha(pilot.PROTOCOL),
                                 "runtime": sha(pilot.RUNTIME)}}
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "sample_outputs_replayed": len(checked)}))


if __name__ == "__main__":
    main()
