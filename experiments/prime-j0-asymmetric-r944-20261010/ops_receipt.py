#!/usr/bin/env python3
"""Verify the paired radix-944/radix-640 source-operation diagnostic."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODULE = Path("src/bin/eisenstein_fixed/unit_orbit_windows.rs")
SOURCE_COMMIT = "d34e5281b38b2b2abbacd8c229f1b3e72263b96a"
FIELDS = (
    "cases", "mixed_additions", "rotations", "point_loads", "atlas_queries",
    "add", "sub", "generic_mul", "square", "solinas", "div5_large",
    "div5_small", "div59_large", "div59_small", "source_limb_products",
)
EXPECTED = {
    "asymmetric_radix944": {
        "cases": 4096, "mixed_additions": 49152, "rotations": 14838,
        "point_loads": 53248, "atlas_queries": 53248,
        "add": 73728, "sub": 333807, "generic_mul": 434176,
        "square": 110592, "solinas": 14838, "div5_large": 0,
        "div5_small": 0, "div59_large": 212992, "div59_small": 106496,
        "source_limb_products": 19952922,
    },
    "mixed_radix640": {
        "cases": 4096, "mixed_additions": 53248, "rotations": 15105,
        "point_loads": 57344, "atlas_queries": 57344,
        "add": 77824, "sub": 360250, "generic_mul": 466944,
        "square": 118784, "solinas": 15105, "div5_large": 131072,
        "div5_small": 65536, "div59_large": 0, "div59_small": 0,
        "source_limb_products": 21433623,
    },
}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def parse_log() -> dict:
    raw = (HERE / "ops-diagnostic.log").read_bytes()
    log = raw.decode()
    assert "asymmetric_radix944_source_operation_diagnostic ..." in log
    assert "test result: ok. 1 passed; 0 failed;" in log
    parsed = {}
    for line in log.splitlines():
        if "mode=" not in line:
            continue
        tokens = dict(token.split("=", 1) for token in line.split()
                      if "=" in token)
        mode = tokens.pop("mode")
        assert mode in EXPECTED and mode not in parsed, mode
        assert set(tokens) == set(FIELDS), (mode, tokens.keys())
        parsed[mode] = {key: int(value) for key, value in tokens.items()}
    assert parsed == EXPECTED, parsed
    for record in parsed.values():
        assert record["source_limb_products"] == (
            36 * (record["generic_mul"] + record["square"])
            + 23 * record["solinas"])
        assert record["point_loads"] == record["mixed_additions"] + 4096
    return parsed


def materialized_source_hashes() -> tuple[str, str]:
    with TemporaryDirectory(prefix="r944-ops-replay-") as temp:
        crate = Path(temp) / "native"
        subprocess.run([sys.executable, str(HERE / "materialize_native.py"),
                        str(crate)], cwd=ROOT, capture_output=True, check=True)
        source = crate / MODULE
        base = source.read_bytes()
        subprocess.run(["patch", "-p1", "-i", str(HERE / "ops-diagnostic.patch")],
                       cwd=crate, capture_output=True, check=True)
        diagnostic = source.read_bytes()
        assert base != diagnostic
        root = str(ROOT).encode()
        assert root in base and root in diagnostic
        return (digest(base.replace(root, b"${ROOT}")),
                digest(diagnostic.replace(root, b"${ROOT}")))


def expected_receipt() -> dict:
    results = parse_log()
    base_hash, diagnostic_hash = materialized_source_hashes()
    candidate = results["asymmetric_radix944"]
    control = results["mixed_radix640"]
    return {
        "schema": 1,
        "status": "passed",
        "timing_class": "source_operation_model_only",
        "source_commit": SOURCE_COMMIT,
        "panel_sha256": digest((HERE / "fresh-inputs.json").read_bytes()),
        "materializer_sha256": digest((HERE / "materialize_native.py").read_bytes()),
        "diagnostic_patch_sha256": digest((HERE / "ops-diagnostic.patch").read_bytes()),
        "diagnostic_log_sha256": digest((HERE / "ops-diagnostic.log").read_bytes()),
        "base_source_normalized_sha256": base_hash,
        "diagnostic_source_normalized_sha256": diagnostic_hash,
        "results": results,
        "candidate_minus_control": {
            key: candidate[key] - control[key] for key in FIELDS if key != "cases"
        },
    }


def main() -> None:
    expected = expected_receipt()
    path = HERE / "ops-diagnostic.json"
    if sys.argv[1:] == ["--write"]:
        assert not path.exists(), "diagnostic receipt already exists"
        path.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
    else:
        assert not sys.argv[1:], "usage: ops_receipt.py [--write]"
        assert json.loads(path.read_text()) == expected
    print(json.dumps({"status": "passed", "source_limb_products_saved":
                      -expected["candidate_minus_control"]["source_limb_products"],
                      "panel_sha256": expected["panel_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
