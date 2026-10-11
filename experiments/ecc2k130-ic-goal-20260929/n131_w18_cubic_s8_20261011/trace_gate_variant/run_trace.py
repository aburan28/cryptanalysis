"""Same N131 public query with exact trace-zero propagation exposed to SAT."""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import circuit as method  # noqa: E402

spec = importlib.util.spec_from_file_location('frozen_n131_cubic_base_run', PARENT/'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_sources = base.sources()
original_build = base.build
original_profile = base.profile


def sources():
    return {**{f'base_{name}': path for name, path in original_sources.items()},
            'trace_runner.py': Path(__file__),
            'trace_gate_result.json': PARENT/'trace_gate_result.json',
            'base_protocol.json': PARENT/'protocol.json',
            'variant_fixture.json': HERE/'fixture.json'}


def build(target_zs):
    c, m, elapsed = original_build(target_zs)
    field = method.Field()
    trace_basis = [method.old.trace(field, 1 << bit) for bit in range(method.N)]
    for coordinate in (*m['pair_z'], *m['middle_z']):
        wire = c.xor(item for item, trace_bit in zip(coordinate, trace_basis) if trace_bit)
        c.require_zero([wire])
    if len(target_zs) == 4:
        assert len(m['target_flags']) == 2
        c.require_zero([m['target_flags'][1]])
    m['direct_trace_zero_rows'] = 6
    m['excluded_trace_one_raw_preimages'] = 2 if len(target_zs) == 4 else 0
    return c, m, elapsed


def profile(c, m, elapsed):
    return {**original_profile(c, m, elapsed),
            'direct_trace_zero_rows': m['direct_trace_zero_rows'],
            'excluded_trace_one_raw_preimages': m['excluded_trace_one_raw_preimages']}


base.HERE = HERE
base.sources = sources
base.build = build
base.profile = profile


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'control', 'query'))
    mode = parser.parse_args().mode
    {'freeze': base.freeze, 'control': base.control, 'query': base.query}[mode]()
