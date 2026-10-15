#!/usr/bin/env python3
"""Replay the frozen A/A and paired-bootstrap audit for the 15-position panel."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014' / 'analyze_tier1.py'
spec = importlib.util.spec_from_file_location('radix_tier1_audit',PARENT)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
auditor.HERE = HERE
auditor.PANELS = {
    96: ('2481bd3c0f7e491698694ccb039f1048',
         'tier1-rules.json','tier1-manifest.json'),
}


if __name__ == '__main__':
    result = auditor.audit(96)
    result['radix15_over_radix16_throughput_median'] = result[
        'descriptive_reference_over_candidate_median']
    result['ratio_definition'] = (
        'reference radix16 online wall time / candidate radix15 online wall time '
        '= candidate radix15 throughput / reference radix16 throughput')
    print(json.dumps(result,sort_keys=True,indent=2))
