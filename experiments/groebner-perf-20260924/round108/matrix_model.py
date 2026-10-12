"""Exact reference matrix replay followed by bounded parity proof compression."""
import importlib.util
from pathlib import Path
from parity_model import rewrite, FIELDS

import scalar_model as previous


def model(n, rows, degree, multiplier_degree, *, minimal=True, parity=False,
          parity_mode=1, parity_bytes=8388608, **limits):
    result = previous.model(n, rows, degree, multiplier_degree, minimal=minimal, **limits)
    if not parity:
        return result
    stats = dict.fromkeys(FIELDS, 0)
    stats['mode'] = parity_mode
    result['parity'] = stats
    if result['stats']['status']:
        return result
    rewritten = rewrite(result['proof'], len(rows), mode=parity_mode,
        max_bytes=parity_bytes, max_work=limits.get('max_work', 20000000)-result['stats']['work'])
    result['parity'] = rewritten['stats']
    result['stats']['work'] += rewritten['stats']['work']
    if rewritten['status']:
        result.update(basis=None, proof=None, reason=rewritten['reason'])
        result['stats']['status'] = rewritten['status']
    else:
        result['proof'] = rewritten['proof']
        result['stats']['output_nodes'] = len(result['proof']['nodes'])
    return result
