#!/usr/bin/env python3
"""Replay the frozen A/A and paired-bootstrap audit for the unit-basis panel."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014' / 'analyze_tier1.py'
spec = importlib.util.spec_from_file_location('radix_tier1_audit', PARENT)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
auditor.HERE = HERE
auditor.PANELS = {
    96: ('393dd4e822084bca846e4a6dd9192389',
         'tier1-rules.json', 'tier1-manifest.json'),
}


if __name__ == '__main__':
    result = auditor.audit(96)
    result['split_over_orbit_throughput_median'] = result[
        'descriptive_reference_over_candidate_median']
    result['ratio_definition'] = (
        'reference orbit online wall time / candidate split online wall time '
        '= candidate split throughput / reference orbit throughput')
    print(json.dumps(result, sort_keys=True, indent=2))
