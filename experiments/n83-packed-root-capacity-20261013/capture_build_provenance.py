#!/usr/bin/env python3
"""Rebuild the pinned clean source separately and compare executable bytes."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-packed-root-crypto-20261013'))
BIN = Path(os.environ.get('N83_BIN_DIR',
    '/Volumes/SSD990/llm/tmp/n83-base-size-cargo-target/release/examples'))
TARGET = Path(os.environ.get('N83_REBUILD_TARGET',
    '/Volumes/SSD990/llm/tmp/n83-packed-capacity-rebuild-target'))
EXAMPLES = {'ic': 'koblitz_orbit_dlp_fast',
            'rho': 'n83_rho_optimization_eval'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def main():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    manifest = json.loads((HERE / 'binary_manifest.json').read_text())
    assert capture(['git', 'rev-parse', 'HEAD'], cwd=CRYPTO) == protocol['source_commit']
    assert capture(['git', 'status', '--porcelain=v1'], cwd=CRYPTO) == ''
    assert sha(CRYPTO / 'examples/koblitz_orbit_dlp_fast.rs') == protocol['ic_source_sha256']
    assert sha(CRYPTO / 'examples/n83_rho_optimization_eval.rs') == protocol['rho_source_sha256']
    assert sha(CRYPTO / 'Cargo.lock') == protocol['cargo_lock_sha256']
    assert {kind: sha(BIN / name) for kind, name in EXAMPLES.items()} == {
        'ic': manifest['ic_sha256'], 'rho': manifest['rho_sha256']}
    assert not TARGET.exists(), 'rebuild target must be new and empty'
    assert shutil.disk_usage(TARGET.parent).free > 5 * (1 << 30)
    environment = os.environ.copy()
    for name in list(environment):
        if name in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_TARGET') or name.startswith('CARGO_PROFILE_'):
            environment.pop(name)
    environment['CARGO_TARGET_DIR'] = str(TARGET)
    environment['TMPDIR'] = str(TARGET.parent)
    command = ['cargo', 'build', '--release', '--locked', '--offline',
               '--example', EXAMPLES['ic'], '--example', EXAMPLES['rho']]
    result = subprocess.run(command, cwd=CRYPTO, env=environment,
                            text=True, capture_output=True)
    (HERE / 'rebuild_stdout.txt').write_text(result.stdout)
    (HERE / 'rebuild_stderr.txt').write_text(result.stderr)
    rebuilt = {kind: sha(TARGET / 'release/examples' / name)
               for kind, name in EXAMPLES.items()} if result.returncode == 0 else None
    receipt = {
        'schema': 'n83_a1_post_run_reproducible_build_v1',
        'audit_phase': 'post_run_independent_rebuild',
        'source_commit': protocol['source_commit'],
        'source_tree_status': 'clean',
        'source_sha256': {
            'ic': protocol['ic_source_sha256'],
            'rho': protocol['rho_source_sha256'],
            'cargo_lock': protocol['cargo_lock_sha256']},
        'cargo_version': capture(['cargo', '--version']),
        'rustc_verbose_version': capture(['rustc', '-vV']),
        'build_command': command,
        'build_environment_overrides': {'CARGO_TARGET_DIR': 'new_empty_target',
                                         'TMPDIR': 'workspace_volume',
                                         'RUSTFLAGS': 'unset',
                                         'CARGO_ENCODED_RUSTFLAGS': 'unset',
                                         'CARGO_BUILD_TARGET': 'unset',
                                         'CARGO_PROFILE_*': 'unset'},
        'build_exit_code': result.returncode,
        'rebuild_stdout_sha256': sha(HERE / 'rebuild_stdout.txt'),
        'rebuild_stderr_sha256': sha(HERE / 'rebuild_stderr.txt'),
        'executed_binary_sha256': {'ic': manifest['ic_sha256'],
                                   'rho': manifest['rho_sha256']},
        'rebuilt_binary_sha256': rebuilt,
        'byte_identical': (rebuilt == {'ic': manifest['ic_sha256'],
                                       'rho': manifest['rho_sha256']}) if rebuilt else False,
        'historical_boundary': 'The pre-run launcher checked the clean source and built both executables offline; this separate post-run build confirms byte reproducibility on the same compiler host.',
    }
    with (HERE / 'build_provenance.json').open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': 'PASS' if receipt['byte_identical'] else 'MISMATCH',
                      'rebuilt_binary_sha256': rebuilt}))
    if not receipt['byte_identical']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
