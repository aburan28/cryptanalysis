#!/usr/bin/env python3
"""Audit each arm and A/A gate of the 128-output batch inversion panel."""

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
    96: ("174c6ea48bab420a9f19f745c9381f16",
         "tier1-batch-rules.json", "tier1-batch-manifest.json"),
}


if __name__ == "__main__":
    result = auditor.audit(96)
    result["batch_inverse_over_individual_throughput_median"] = result[
        "descriptive_reference_over_candidate_median"]
    result["ratio_definition"] = (
        "reference individual-inversion online wall time / candidate shared-inversion "
        "online wall time = shared-inversion batch throughput / individual-inversion throughput"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
