#!/usr/bin/env python3
"""Audit the ordered-versus-fixed fourteen-position Tier 1 panel."""

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
    96: ("895830fdb95347f5873a7f35656e5a1c",
         "tier1-ordered-rules.json", "tier1-ordered-manifest.json"),
}


if __name__ == "__main__":
    result = auditor.audit(96)
    result["ordered14_over_fixed14_throughput_median"] = result[
        "descriptive_reference_over_candidate_median"]
    result["ratio_definition"] = (
        "reference fixed14 online wall time / candidate ordered14 online wall time "
        "= ordered14 throughput / fixed14 throughput"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
