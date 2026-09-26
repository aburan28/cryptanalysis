"""Build and retain one bounded local Metal screen, including failed outcomes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=['local', 'profile', 'baseline', 'confirm'], default='local')
    parser.add_argument('--label', required=True)
    parser.add_argument('--m4ri-prefix', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--panel-width', type=int, choices=[8, 16], default=8)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_-]+', args.label) or args.timeout <= 0:
        parser.error('Use a simple label and a positive timeout.')
    if args.panel_width != 8 and args.variant not in ['local', 'confirm']:
        parser.error('Wider panels apply only to the local variant.')
    result = HERE / 'results' / (args.label + '.json')
    receipt_path = HERE / 'results' / (args.label + '-receipt.json')
    log = result.with_suffix('.log')
    if any(p.exists() for p in [result, receipt_path, log]):
        parser.error('Label already exists; retained outcomes must not be overwritten.')
    build = HERE / 'build' / args.label
    build.mkdir(parents=True, exist_ok=False)
    snapshots = HERE / 'results' / 'sources' / args.label
    snapshots.mkdir(parents=True, exist_ok=False)
    source = HERE / ('profile_rref.mm' if args.variant == 'profile' else 'local_rref.mm')
    shader = HERE / 'local_panel.metal'
    dependencies = []
    if args.variant == 'confirm':
        source = HERE / 'confirm.mm'
        dependencies = [HERE / 'local_rref.mm', HERE.parent / 'round6/fused_rref.mm',
                        HERE.parent / 'round6/fused_rref.metal']
    if args.variant == 'baseline':
        source = HERE.parent / 'round6/fused_rref.mm'
        shader = HERE.parent / 'round6/fused_rref.metal'
    for path in [source, shader, Path(__file__), *dependencies]:
        shutil.copy2(path, snapshots / path.name)
    compiled_shader = build / 'shader.metal'
    compiled_shader.write_text('#define PANEL_WIDTH ' + str(args.panel_width) + '\n' + shader.read_text())
    matrix_gz = HERE.parent / 'round3/matrices.json.gz'
    matrices = build / 'matrices.json'
    matrices.write_bytes(gzip.decompress(matrix_gz.read_bytes()))
    binary = build / 'rref'
    compiler = os.environ.get('CXX', 'clang++')
    compile_command = [compiler, '-O3', '-std=c++17', '-fobjc-arc', '-DFUSED=0',
                       '-DPIVOT_THREADS=256', '-DM4RI_K=5', '-DPANEL_WIDTH=' + str(args.panel_width), str(source),
                       '-I' + str(args.m4ri_prefix / 'include'),
                       '-L' + str(args.m4ri_prefix / 'lib'), '-lm4ri',
                       '-framework', 'Foundation', '-framework', 'Metal', '-o', str(binary)]
    command = [str(binary), str(compiled_shader), str(matrices)]
    if args.variant == 'confirm':
        command.append(str(HERE.parent / 'round6/fused_rref.metal'))
    record = {
        'status': 'building', 'variant': args.variant, 'start_utc': utc(),
        'platform': platform.platform(), 'python': sys.version,
        'load_start': os.getloadavg(), 'compile_command': compile_command, 'command': command,
        'source_sha256': {str(p.relative_to(HERE)): sha(p) for p in snapshots.iterdir()},
        'matrix_sha256': sha(matrices), 'matrix_gz_sha256': sha(matrix_gz),
        'compiled_shader_sha256': sha(compiled_shader), 'panel_width': args.panel_width,
        'm4ri_sha256': sha(args.m4ri_prefix / 'lib/libm4ri.dylib'),
        'scope': 'one-matrix diagnostics, not a complete polynomial query or IC comparison',
        'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
        'memory_peak_bytes': None, 'timeout_seconds': args.timeout,
    }

    def save():
        receipt_path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')

    save()
    try:
        compile_result = subprocess.run(compile_command, capture_output=True, text=True, timeout=120)
        record['compiler_output'] = compile_result.stdout + compile_result.stderr
        record['compile_returncode'] = compile_result.returncode
        if compile_result.returncode:
            record['status'] = 'build_failed'
        else:
            record['binary_sha256'] = sha(binary)
            record['status'] = 'running'
            record['run_start_utc'] = utc()
            record['run_load_start'] = os.getloadavg()
            save()
            with result.open('x') as out, log.open('x') as err:
                completed = subprocess.run(command, stdout=out, stderr=err, timeout=args.timeout)
            record['returncode'] = completed.returncode
            record['status'] = 'PASS' if completed.returncode == 0 else 'failed'
            record['result_sha256'] = sha(result)
            if completed.returncode == 0:
                data = json.loads(result.read_text())
                if data.get('exact_rref_and_rank') is not True:
                    raise ValueError('Missing exact RREF/rank qualification')
                record['checked_matrices'] = data['checked_matrices']
    except subprocess.TimeoutExpired:
        record['status'] = 'timeout'
    except Exception as exc:
        record['status'] = 'error'
        record['error'] = str(exc)
    finally:
        record['end_utc'] = utc()
        record['load_end'] = os.getloadavg()
        save()
    print(json.dumps({'status': record['status'], 'receipt': str(receipt_path)}, indent=2))
    return 0 if record['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
