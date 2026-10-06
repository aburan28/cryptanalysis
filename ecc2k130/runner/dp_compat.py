#!/usr/bin/env python3
"""Retain stricter distinguished endpoints from a corpus of the SAME walk.

This preserves eligible records; it does not extend discarded trails, convert
between iteration functions, or modify S3/RDS. Both formats are 32-byte records.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import os

RECORD = struct.Struct("<4Q")
popcount = getattr(int, "bit_count", lambda value: bin(value).count("1"))


def reconcile(source, destination, source_config, target_config):
    for name in ("curve", "walkId", "recordFormat"):
        if not source_config.get(name) or source_config.get(name) != target_config.get(name):
            raise ValueError(f"incompatible {name}; cutoff filtering cannot convert walks")
    if source_config["curve"] != 131 or source_config["recordFormat"] != "gpu-packed32":
        raise ValueError("only ECC2K-130 gpu-packed32 records are supported")
    old, new = source_config.get("dpWeight"), target_config.get("dpWeight")
    if type(old) is not int or type(new) is not int or not 0 <= new <= old <= 131:
        raise ValueError("target cutoff must be no larger than the source cutoff")
    source, destination = Path(source), Path(destination)
    if destination.exists() or source.resolve() == destination.resolve():
        raise ValueError("destination must be a new file")
    source_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    count = kept = 0
    histogram = {}
    # Complete validation before publishing, and never replace an existing file.
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        staging = Path(tmp.name)
        try:
            with source.open("rb") as stream:
                while blob := stream.read(RECORD.size * 8192):
                    if len(blob) % RECORD.size:
                        raise ValueError("source contains a partial record")
                    source_hash.update(blob)
                    for offset in range(0, len(blob), RECORD.size):
                        record = blob[offset:offset+RECORD.size]
                        _, a, b, c = RECORD.unpack(record)
                        if c >> 3:
                            raise ValueError("point key exceeds 131 bits")
                        weight = popcount(a) + popcount(b) + popcount(c)
                        if weight > old:
                            raise ValueError("record violates the declared source cutoff")
                        count += 1
                        histogram[weight] = histogram.get(weight, 0) + 1
                        if weight <= new:
                            tmp.write(record)
                            output_hash.update(record)
                            kept += 1
            tmp.flush()
            os.fsync(tmp.fileno())
            os.link(staging, destination)
        finally:
            staging.unlink(missing_ok=True)
    return {"walkId": source_config["walkId"], "source_dp_weight": old, "target_dp_weight": new,
            "source_records": count, "retained_records": kept, "not_retained_records": count-kept,
            "source_sha256": source_hash.hexdigest(), "output_sha256": output_hash.hexdigest(),
            "source_weight_histogram": histogram,
            "limitation": "Retains eligible endpoints only; other trails require replay/continuation."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--source-config", required=True)
    p.add_argument("--target-config", required=True)
    args = p.parse_args()
    result = reconcile(args.input, args.output,
        json.loads(Path(args.source_config).read_text()), json.loads(Path(args.target_config).read_text()))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
