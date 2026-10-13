#!/usr/bin/env python3
"""Compile the exact Rust table-slot type on this run's ARM64 target."""

import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'slot_layout.rs'
TMP_ROOT = Path('/Volumes/SSD990/llm/tmp')


def main():
    compiler = subprocess.run(['rustc', '-vV'], text=True,
                              capture_output=True, check=True)
    assert 'host: aarch64-apple-darwin' in compiler.stdout
    assert platform.machine() == 'arm64'
    with tempfile.TemporaryDirectory(prefix='n83-slot-layout-', dir=TMP_ROOT) as folder:
        binary = Path(folder) / 'slot_layout'
        environment = os.environ.copy()
        environment['TMPDIR'] = folder
        build = subprocess.run(['rustc', '--edition=2021', str(SOURCE),
                                '-O', '-o', str(binary)],
                               text=True, capture_output=True, env=environment)
        assert build.returncode == 0 and build.stderr == ''
        result = subprocess.run([str(binary)], text=True,
                                capture_output=True, check=True)
        assert result.stdout == '32\n' and result.stderr == ''
        receipt = {
            'schema': 'n83_root_table_slot_layout_v1',
            'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'compiler_command': ['rustc', '--edition=2021', 'slot_layout.rs', '-O'],
            'rustc_verbose_version': compiler.stdout,
            'compiler_exit_code': build.returncode,
            'compiler_stdout': build.stdout,
            'compiler_stderr': build.stderr,
            'program_stdout': result.stdout,
            'program_stderr': result.stderr,
            'slot_type': '(u128, u64)',
            'slot_bytes': 32,
            'target_architecture': platform.machine(),
        }
    with (HERE / 'slot_layout_receipt.json').open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': 'PASS', 'slot_bytes': receipt['slot_bytes']}))


if __name__ == '__main__':
    main()
