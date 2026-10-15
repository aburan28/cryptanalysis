#!/usr/bin/env python3
"""Replay every arm and A/A gate of the fixed-14 native timing panel."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-variable-orbit-radix-20261014" / "analyze_tier1.py"
spec = importlib.util.spec_from_file_location("radix_tier1_audit", PARENT)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
auditor.HERE = HERE
auditor.PANELS = {
    96: ("3a7f28ad0dfa4444bf3b141421ccba16",
         "tier1-fixed14-rules.json", "tier1-fixed14-manifest.json"),
}


if __name__ == "__main__":
    result = auditor.audit(96)
    result["fixed14_over_radix15_throughput_median"] = result[
        "descriptive_reference_over_candidate_median"]
    result["ratio_definition"] = (
        "reference radix15 online wall time / candidate fixed radix14 online wall time "
        "= candidate fixed radix14 throughput / reference radix15 throughput"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
