"""Exact scratch-reuse producer/checker controls beyond 20 variables."""
import argparse
import copy
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess

from scratch_query import HERE, ScratchNative, P, abi
from native import Native, SeededStats


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source():
    root = HERE.parents[2]
    for path in HERE.glob('*.py'):
        assert path.read_bytes() == subprocess.check_output(
            ['git', 'show', 'HEAD:'+str(path.relative_to(root))], cwd=root)


def solve(native, original, seed, checker):
    stats = SeededStats()
    native.reset() if isinstance(native, ScratchNative) else None
    handle = native.lib.seeded_produce(C.byref(original.view), C.byref(seed),
                                      20_000_000, 200_000, 4096, 64, 0, C.byref(stats))
    assert handle, native.lib.seeded_error().decode()
    try:
        view = native.lib.seeded_view(handle).contents
        certificate = checker._check(original.view, view, 20_000_000, 2_000_000)
        assert certificate['verified'] is True
        basis, proof = abi.export(view)
        return dict(basis=basis, proof=proof, producer=abi.fields(stats.producer),
                    work=stats.work, certificate=certificate)
    finally:
        native.lib.seeded_destroy(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check_source()
    baseline, scratch, checker = Native(), ScratchNative(), abi.PackedProof()
    build = json.loads((HERE/'build/receipt.json').read_text())
    assert sha(scratch.path) == build['binaries'][scratch.path.name]
    rows = []
    for n in (21, 32, 64):
        equations = [[1 << i] for i in range(8)]
        original = abi.InputOwner(n, len(equations), abi.anf_from_equations(equations))
        offsets = (abi.U64 * 1)(0)
        seed = abi.ProofView(1, n, 1, 0, 0, 0, 0, None, offsets, None, None)
        old = solve(baseline, original, seed, checker)
        new = solve(scratch, original, seed, checker)
        assert new['basis'] == old['basis']
        assert new['producer']['matrices'] >= old['producer']['matrices'] + 1
        corrupt = copy.deepcopy(new['proof'])
        assert len(corrupt['outputs']) >= 2
        corrupt['outputs'][0] = corrupt['outputs'][1]
        forged = abi.ProofOwner(n, new['basis'], corrupt)
        rejection = checker._check(original.view, forged.view, 20_000_000, 2_000_000)
        assert rejection['status'] == 'rejected' and rejection['verified'] is False
        rows.append(dict(nvars=n, equations=len(equations),
                         baseline_work=old['work'], scratch_work=new['work'],
                         basis=new['basis'], checker_work=new['certificate']['stats']['work'],
                         checker_field_pairs=new['certificate']['stats']['field_pairs'],
                         corrupted_output_rejected=True))
    record = dict(status='PASS', rows=rows, reference_root=str(P.parents[1]),
                  scratch_binary_sha256=sha(scratch.path),
                  checker_binary_sha256=sha(checker.checker_path),
                  timing_eligible=False, qualified_speedup=None)
    assert not args.output.exists()
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print('F4_ROW_SCRATCH_LARGE_PROOF_PASS', len(rows), flush=True)


if __name__ == '__main__':
    main()
