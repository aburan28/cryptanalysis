#!/usr/bin/env python3
"""Materialize the checked width-16 canonical x set in key order."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "ecc2k130/runner/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]

import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from fast_x import CanonicalXFromOrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "d16_canonical_x.bin"
    receipt_path = HERE / "materialization.json"
    assert not output.exists() and not receipt_path.exists()
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    assert result["status"] == "PASS"
    assert result["protocol_sha256"] == sha(protocol_path)
    key_path = ROOT / protocol["key_file"]
    assert sha(key_path) == protocol["key_sha256"]
    data = key_path.read_bytes()
    assert len(data) == 21 * protocol["K"]
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert keys == sorted(set(keys))
    onb = field.Onb(83)
    orbit = OrbitKey(onb)
    lookup = CanonicalXFromOrbitKey(orbit)
    values = [lookup.canonical_x(key) for key in keys]
    assert len(set(values)) == protocol["K"]
    payload = b"".join(value.to_bytes(11, "little") for value in values)
    assert hashlib.sha256(payload).hexdigest() == result[
        "reference_digest_sha256"] == result["cycle_table_digest_sha256"]
    with output.open("xb") as stream:
        stream.write(payload)
    receipt = {
        "kind": "n83_width16_canonical_x_materialization",
        "status": "PASS",
        "K": protocol["K"],
        "B": protocol["B"],
        "key_sha256": sha(key_path),
        "canonical_x_file": output.name,
        "canonical_x_sha256": sha(output),
        "canonical_x_bytes": len(payload),
        "protocol_sha256": sha(protocol_path),
        "lookup_result_sha256": sha(result_path),
        "source_sha256": {
            "materialize.py": sha(Path(__file__)),
            "fast_x.py": sha(HERE / "fast_x.py"),
        },
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "K": protocol["K"],
                      "bytes": len(payload)}))


if __name__ == "__main__":
    main()
