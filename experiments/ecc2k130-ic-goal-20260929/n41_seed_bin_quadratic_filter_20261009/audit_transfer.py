#!/usr/bin/env python3
"""Independent integer audit of the literal N131 W18 transfer calculation."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTIER = HERE / "../first_pair_generation_frontier.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "transfer_audit.json"
    if output.exists():
        raise FileExistsError("preserve first transfer audit")
    frozen = json.loads((HERE / "transfer_audit_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"transfer-audit input changed: {name}")
    if sha(Path(__file__)) != frozen["audit_source_sha256"]:
        raise ValueError("transfer-audit source changed")
    transfer = json.loads((HERE / "transfer_result.json").read_text())
    frontier = json.loads(FRONTIER.read_text())["n131"]
    if (sha(FRONTIER) != frozen["frontier_sha256"] or
            transfer["curve_id"] != frontier["curve_id"]):
        raise ValueError("N131 frontier identity changed")
    seed_values = (1 << frozen["seed_bits"]) - 1
    bins = seed_values**2
    bits = (1 + frozen["coordinate_bits"] +
            (frozen["coordinate_bits"] * (frozen["coordinate_bits"] - 1)) // 2)
    words = -(-bits // 64)
    payload = (4 + frozen["equations_per_bin"] * words * 8) * bins
    cap = frozen["rss_cap_bytes"]
    states = frontier["distinct_column_pair_states_lower"]
    checks = {
        "literal_seed_bins": bins,
        "quadratic_features_per_bin": bits,
        "words_per_equation": words,
        "literal_filter_table_bytes": payload,
        "compression_factor_needed_to_fit_4gib_rounded_up": -(-payload // cap),
        "one_bit_per_pair_state_domain_bytes_lower": -(-states // 8),
        "literal_suffix_pair_pair_combinations_lower": states**2,
        "literal_suffix_pair_pair_combinations_per_second_in_600s_lower_rounded_up":
            -(-(states**2) // frozen["wall_cap_seconds"]),
    }
    if any(transfer[name] != value for name, value in checks.items()):
        raise ValueError("independent literal transfer arithmetic differs")
    if (Fraction(payload, cap) <= 1 or
            Fraction(states, 8 * cap) <= 1 or
            transfer["status"] != "FAIL_LITERAL_N131_W18_MEMORY_AND_WORK_GATE"):
        raise ValueError("resource-gate decision differs")
    audit = {
        "status": "PASS_INDEPENDENT_LITERAL_N131_TRANSFER_ARITHMETIC",
        "curve_id": transfer["curve_id"],
        "checked_fields": len(checks),
        "filter_table_over_memory_cap": True,
        "one_bit_pair_domain_over_memory_cap": True,
        "transfer_protocol_sha256": sha(HERE / "transfer_protocol.json"),
        "transfer_result_sha256": sha(HERE / "transfer_result.json"),
        "transfer_audit_protocol_sha256": sha(HERE / "transfer_audit_protocol.json"),
    }
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
