#!/usr/bin/env python3
"""Cross-check the packed portable GF(2^131) backend on exhaustive d10."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTROL = HERE / "controls/d10-b2048"
SOURCE = HERE / "enumerate.cpp"
STREAMS = ("membership.bin",)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    summary = json.loads((CONTROL / "summary.json").read_text())
    assert summary["dimension"] == 10
    assert json.loads((CONTROL / "verification.json").read_text())["verified"]
    with tempfile.TemporaryDirectory(prefix="ecc2k130-w10-portable-") as temp:
        folder = Path(temp)
        binary = folder / "enumerate"
        build = ["clang++", "-U__ARM_FEATURE_CRYPTO", "-O3", "-std=c++17",
                 "-Wall", "-Wextra", "-Wconversion", "-Werror", str(SOURCE),
                 "-o", str(binary)]
        subprocess.run(build, check=True, capture_output=True)
        original_argv = summary["run_argv"]
        command = [str(binary), *original_argv[1:8],
                   *(str(folder / name) for name in STREAMS),
                   str(folder / "native.json")]
        subprocess.run(command, check=True, capture_output=True)
        native = json.loads((folder / "native.json").read_text())
        assert native["field_backend"] == "portable_bitwise"
        assert native["dimension"] == 10
        assert native["checked_nonzero_masks"] == 1023
        for name in ("source", "descendant"):
            assert native[name] == summary[name]
        assert native["paired_rationality"] == summary["paired_rationality"]
        stream_hashes = {}
        for name in STREAMS:
            expected = summary["artifacts_sha256"][name]
            assert sha(CONTROL / name) == expected
            assert sha(folder / name) == expected
            stream_hashes[name] = expected
        result = {
            "schema": "ecc2k130-263-w28-packed-d10-portable-backend-control-v1",
            "status": "PASS_PORTABLE_FULL_D10_MATCH",
            "source_sha256": sha(Path(__file__)),
            "enumerator_sha256": sha(SOURCE),
            "control_summary_sha256": sha(CONTROL / "summary.json"),
            "control_verification_sha256": sha(CONTROL / "verification.json"),
            "compiler": subprocess.run(["clang++", "--version"], check=True,
                                       capture_output=True, text=True).stdout.splitlines()[0],
            "forced_field_backend": native["field_backend"],
            "checked_nonzero_masks": native["checked_nonzero_masks"],
            "stream_sha256": stream_hashes,
            "source_B": native["source"]["actual_usable_points_B"],
            "descendant_B": native["descendant"]["actual_usable_points_B"],
        }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "source_B": result["source_B"],
                      "descendant_B": result["descendant_B"]}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
