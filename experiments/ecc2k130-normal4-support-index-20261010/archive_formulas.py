#!/usr/bin/env python3
"""Store exact selector XCNFs as deterministic gzip with raw-byte replay."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import build_selector as circuit


RUN = circuit.HERE / "runs/R1"
NAMES = ("counter_leaf", "support_index_leaf",
         "counter_m6_four_lift", "support_index_m6_four_lift")


def decompressed_sha(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            count += len(chunk)
    return digest.hexdigest(), count


def inputs() -> list[tuple[Path, str]]:
    entries = [(RUN / (name + ".xcnf"), json.loads(
        (RUN / (name + ".json")).read_text())["formula_sha256"])
        for name in NAMES]
    receipt = json.loads((RUN / "cnf_controls/receipt.json").read_text())
    if receipt["status"] != "PASS_PINNED_ELEVEN_NATIVE_XOR_CONTROLS":
        raise ValueError("native-XOR controls changed")
    entries.extend((RUN / "cnf_controls" /
                    (row["policy"] + "_" + row["case"] + ".xcnf"),
                    row["formula_sha256"]) for row in receipt["results"])
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    archive_receipt = RUN / "archives.json"
    if not args.verify and archive_receipt.exists():
        parser.error("refusing to overwrite archive receipt")
    rows = []
    for raw, expected in inputs():
        archive = raw.with_suffix(".xcnf.gz")
        if not args.verify:
            if not raw.exists() or archive.exists():
                raise ValueError("raw formula or archive state changed: " + str(raw))
            if circuit.ref.sha(raw) != expected:
                raise ValueError("raw formula differs from build receipt")
            with raw.open("rb") as source, archive.open("xb") as destination:
                with gzip.GzipFile(filename="", mode="wb", fileobj=destination,
                                   mtime=0, compresslevel=9) as stream:
                    for chunk in iter(lambda: source.read(1 << 20), b""):
                        stream.write(chunk)
        replay_sha, replay_bytes = decompressed_sha(archive)
        if replay_sha != expected:
            raise ValueError("decompressed XCNF differs from receipt")
        rows.append({
            "path": str(archive.relative_to(circuit.ROOT)),
            "raw_formula_sha256": replay_sha,
            "raw_formula_bytes": replay_bytes,
            "archive_sha256": circuit.ref.sha(archive),
            "archive_bytes": archive.stat().st_size,
        })
    record = {
        "schema": "ecc2k130-normal4-selector-archives-v1",
        "status": "PASS_DETERMINISTIC_ARCHIVE_REPLAY",
        "candidate_id": None,
        "archiver_sha256": circuit.ref.sha(Path(__file__)),
        "archive_count": len(rows),
        "archives": rows,
    }
    if args.verify:
        if record != json.loads(archive_receipt.read_text()):
            raise ValueError("archive receipt differs from current files")
    else:
        archive_receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        for raw, _ in inputs():
            raw.unlink()
    print("PASS_ARCHIVES", len(rows))


if __name__ == "__main__":
    main()
