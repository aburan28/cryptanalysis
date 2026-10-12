#!/usr/bin/env python3
"""Attest exact edits after the completed ARM64 serial replay."""

import copy
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PREFIX = "experiments/prime-j0-staged-prefetch-20261010/"
PROTOCOL = PREFIX + "PROTOCOL.md"
CHECKER = PREFIX + "verify_candidate.py"
AMENDER = PREFIX + "amend_receipt.py"
UNIT_MODULE = "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
OLD_PROTOCOL = ("   compared scalar. Record zero selections and failures. Neither arm\n"
                "   allocates a per-scalar heap object. The staged mode uses a fixed\n"
                "   stack array of at most sixteen choices.\n")
NEW_PROTOCOL = ("   compared scalar. Record zero selections and failures. The staged\n"
                "   mode adds no per-scalar heap allocation beyond the shared scalar\n"
                "   selector; its choices use a fixed stack array of at most sixteen.\n")
CHECKER_ADDITION = ("        if any(sha(ROOT / name) != digest\n"
                    "               for name, digest in result[\"source_sha256\"].items()):\n"
                    "            result[\"problems\"].append(\"source changed during verification\")\n")
OLD_X86_PREFETCH = ('    #[cfg(target_arch = "x86_64")]\n'
                    '    {\n'
                    '        use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};\n')
NEW_X86_PREFETCH = ('    #[cfg(target_arch = "x86_64")]\n'
                    '    unsafe {\n'
                    '        use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};\n')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def main():
    initial_path = HERE / "verification-initial.json"
    initial = json.loads(initial_path.read_text())
    assert initial["status"] == "passed" and initial["problems"] == []
    assert initial["native_tests_passed"] == 67
    binary_path = Path(initial["runs"]["candidate-case"]["command"][0])
    assert sha(binary_path) == initial["binary_sha256"]
    sources = initial["source_sha256"]
    protocol_now = (ROOT / PROTOCOL).read_text()
    checker_now = (ROOT / CHECKER).read_text()
    unit_module_now = (ROOT / UNIT_MODULE).read_text()
    assert protocol_now.count(NEW_PROTOCOL) == 1
    assert checker_now.count(CHECKER_ADDITION) == 1
    assert unit_module_now.count(NEW_X86_PREFETCH) == 1
    protocol_before = protocol_now.replace(NEW_PROTOCOL, OLD_PROTOCOL)
    checker_before = checker_now.replace(CHECKER_ADDITION, "")
    unit_module_before = unit_module_now.replace(NEW_X86_PREFETCH, OLD_X86_PREFETCH)
    assert sha_bytes(protocol_before.encode()) == sources[PROTOCOL]
    assert sha_bytes(checker_before.encode()) == sources[CHECKER]
    assert sha_bytes(unit_module_before.encode()) == sources[UNIT_MODULE]
    for name, digest in sources.items():
        if name not in (PROTOCOL, CHECKER, UNIT_MODULE):
            assert sha(ROOT / name) == digest, name
    for label, record in initial["runs"].items():
        assert record["exit_code"] == 0, label
        for stream in ("stdout", "stderr"):
            path = HERE / record[f"{stream}_file"]
            assert sha(path) == record[f"{stream}_sha256"], (label, stream)
    assert initial["runs"]["reference-fixture"]["parsed_cases"] == 129
    assert initial["runs"]["candidate-fixture"]["parsed_cases"] == 129
    assert initial["runs"]["reference-case"]["retained_bytes"] == "78470208"
    assert initial["runs"]["candidate-case"]["retained_bytes"] == "78470208"
    test_stdout = (HERE / initial["runs"]["native_tests"]["stdout_file"]).read_text()
    match = re.search(r"test result: ok\. 67 passed; 0 failed;.*finished in ([0-9.]+)s", test_stdout)
    assert match is not None
    amended = copy.deepcopy(initial)
    amended["verification_method"] = "exact_arm64_binary_preserving_amendment"
    amended["amendment"] = {
        "initial_receipt_file": initial_path.name,
        "initial_receipt_sha256": sha(initial_path),
        "initial_protocol_sha256": sources[PROTOCOL],
        "current_protocol_sha256": sha(ROOT / PROTOCOL),
        "initial_checker_sha256": sources[CHECKER],
        "current_checker_sha256": sha(ROOT / CHECKER),
        "initial_unit_module_sha256": sources[UNIT_MODULE],
        "current_unit_module_sha256": sha(ROOT / UNIT_MODULE),
        "x86_only_unsafe_block_substitution_verified": True,
        "exact_three_substitutions_verified": True,
        "all_recorded_sources_accounted_for": True,
        "all_run_output_hashes_rechecked": True,
        "native_suite_reused": True,
        "native_suite_wall_seconds_from_raw_output": match.group(1),
    }
    amended["source_sha256"][PROTOCOL] = sha(ROOT / PROTOCOL)
    amended["source_sha256"][CHECKER] = sha(ROOT / CHECKER)
    amended["source_sha256"][UNIT_MODULE] = sha(ROOT / UNIT_MODULE)
    amended["source_sha256"][AMENDER] = sha(ROOT / AMENDER)
    for name, digest in amended["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    output = HERE / "verification.json"
    if output.exists():
        raise SystemExit("final receipt already exists")
    output.write_text(json.dumps(amended, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": amended["status"],
                      "verification_method": amended["verification_method"],
                      "initial_receipt_sha256": amended["amendment"]["initial_receipt_sha256"],
                      "binary_sha256": amended["binary_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
