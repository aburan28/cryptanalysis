"""Compare complete scalar walks with normal and polynomial coordinate storage."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import modal

SOURCE = Path(__file__).resolve().parent
app = modal.App('ecc2k130-polynomial-state-timed-comparison')
configs = {'normal': 0, 'polynomial': 1}
fixed = dict(BATCH=32, THREADS=128, MINBLOCKS=4, PACKED_SINGLE_PRODUCT=1,
             PACKED_CACHE_DENOM=1, PACKED_BY_VALUE=1, PACKED_PERM_SIGMA=3,
             PACKED_POLY_CHAIN=1, PACKED_UNROLL_INV=1, PACKED_PAIR_PRODUCTS=1)
commands = ['cd /root/ecc2k130 && make test-timing CXX=g++']
for name, state in configs.items():
    knobs = dict(fixed, PACKED_POLY_STATE=state)
    args = ' '.join(f'{k}={v}' for k, v in knobs.items())
    defs = ' '.join(f'-DECC_{k}={v}' for k, v in knobs.items())
    commands += [
        f'cd /root/ecc2k130 && make -B gpu ARCH="-gencode arch=compute_120,code=sm_120" {args} && cp ecc2k130 /root/{name}',
        f'cd /root/ecc2k130 && nvcc -O3 -std=c++17 -arch=sm_120 {defs} src/testpackedcuda.cu -o /root/check-{name}',
    ]
image = (modal.Image.from_registry('nvidia/cuda:13.0.0-devel-ubuntu24.04', add_python='3.12')
         .entrypoint([]).apt_install('build-essential')
         .add_local_dir(str(SOURCE), remote_path='/root/ecc2k130', copy=True)
         .run_commands(*commands))
volume = modal.Volume.from_name('ecc2k130', create_if_missing=True)


def source_identity(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()
            and p.name not in ('ecc2k130', 'ecc2k130-cpu')
            and '__pycache__' not in p.relative_to(root).parts
            and 'build' not in p.relative_to(root).parts and p.suffix not in ('.pyc', '.o')}


@app.function(image=image, gpu='RTX-PRO-6000', cpu=4, timeout=3600,
              volumes={'/data': volume})
def run(expected_source):
    root = Path('/root/ecc2k130')
    sys.path.insert(0, str(root / 'codegen'))
    from benchreport import benchResult, summarizeSamples
    result = dict(valid=False, finalReseedSynchronized=True, kind='complete scalar walk comparison', configs=configs,
                  fixed=fixed, arithmetic={}, integration={}, screen=[], confirmation={},
                  collection={}, steps=1024, launches=32,
                  compiler=subprocess.check_output(['nvcc', '--version'], text=True),
                  gpu=subprocess.check_output(['nvidia-smi', '--query-gpu=name,uuid,driver_version,pstate,clocks.current.sm,clocks.current.memory,power.limit,temperature.gpu', '--format=csv'], text=True),
                  binaries={name: hashlib.sha256(Path('/root', name).read_bytes()).hexdigest() for name in configs},
                  sourceFiles=source_identity(root))

    def execute(command, timeout=600):
        p = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        return dict(command=command, returncode=p.returncode, output=p.stdout + p.stderr)

    try:
        if result['sourceFiles'] != expected_source:
            raise RuntimeError('remote source differs from frozen local source')
        for name in configs:
            print('ARITHMETIC ' + name, flush=True)
            row = execute(['/root/check-' + name], 180)
            result['arithmetic'][name] = row
            print(json.dumps(row), flush=True)
            if row['returncode']:
                raise RuntimeError('GPU arithmetic failed: ' + name)
            print('INTEGRATION ' + name, flush=True)
            row = execute(['python3', 'codegen/testpackedclient.py', '/root/' + name])
            result['integration'][name] = row
            print(json.dumps(row), flush=True)
            if row['returncode']:
                raise RuntimeError('GPU integration failed: ' + name)
        print('CROSS-MODE CHECKPOINTS', flush=True)
        row = execute(['python3', 'codegen/testpolystate.py', '/root/normal', '/root/polynomial'], 1200)
        result['crossMode'] = row
        print(json.dumps(row), flush=True)
        if row['returncode']:
            raise RuntimeError('cross-mode compatibility failed')

        row = execute(['/root/normal', '--packed', '--curve', '131', '--bench',
                       '--steps', '1', '--launches', '1', '--verify', '0'], 60)
        result['workerProbe'] = row
        match = re.search(r'backend cuda-packed131: (\d+) threads x (\d+) slots x 1 lanes = (\d+) walks,', row['output'])
        if row['returncode'] or not match:
            raise RuntimeError('control worker probe failed')
        threads, batch, walks = map(int, match.groups())
        if batch != fixed['BATCH'] or walks != threads * batch:
            raise RuntimeError('worker accounting disagrees')
        result['workerThreads'] = threads
        result['expectedIterations'] = walks * 1024 * 32

        def sample(name, corpus=None):
            cmd = ['/root/' + name, '--packed', '--curve', '131', '--threads', str(threads),
                   '--steps', '1024', '--launches', '32', '--verify', '0']
            cmd += ['--bench'] if corpus is None else ['--dp-weight', '34', '--dp-file', str(corpus)]
            raw = execute(cmd, 240)
            row = benchResult(cmd, raw['returncode'], raw['output'])
            counts = re.findall(r'(\d+) iterations\s+\d+ dp', raw['output'])
            row.update(name=name, expectedIterations=result['expectedIterations'],
                       reportedIterations=int(counts[-1]) if counts else None)
            row['valid'] = row['valid'] and row['reportedIterations'] == row['expectedIterations']
            if corpus is not None:
                data = corpus.read_bytes() if corpus.exists() else b''
                final = re.findall(r'finished:.*?, (\d+) distinguished points '
                                   r'\(0 verified against the reference, (\d+) dropped\)', raw['output'])
                row.update(corpusBytes=len(data), corpusRecords=len(data) // 32,
                           sortedCorpusSha256=hashlib.sha256(b''.join(sorted(data[i:i+32] for i in range(0, len(data), 32)))).hexdigest())
                row['valid'] = (row['valid'] and len(final) == 1 and int(final[0][0]) > 0
                                and int(final[0][1]) == 0 and len(data) == int(final[0][0]) * 32)
            if not row['valid']:
                row['rate'] = 0.0
            print(json.dumps(row), flush=True)
            return row

        for name in ('normal', 'polynomial', 'normal'):
            print('SCREEN ' + name, flush=True)
            row = sample(name)
            result['screen'].append(row)
            if not row['valid']:
                raise RuntimeError('incomplete benchmark: ' + name)
        controls = [r['rate'] for r in result['screen'] if r['name'] == 'normal']
        candidate = result['screen'][1]['rate']
        if candidate > max(controls) * 1.005:
            result['screenWinner'] = 'polynomial'
            result['confirmation'] = {name: [] for name in configs}
            for repeat in range(3):
                for name in (('polynomial', 'normal') if repeat % 2 == 0 else ('normal', 'polynomial')):
                    print(f'CONFIRM {repeat + 1}/3 ' + name, flush=True)
                    row = sample(name)
                    result['confirmation'][name].append(row)
                    if not row['valid']:
                        raise RuntimeError('incomplete confirmation: ' + name)
            result['summary'] = {name: summarizeSamples(rows) for name, rows in result['confirmation'].items()}
            result['collection'] = {name: [] for name in configs}
            for repeat in range(3):
                for name in (('normal', 'polynomial') if repeat % 2 == 0 else ('polynomial', 'normal')):
                    print(f'COLLECTION {repeat + 1}/3 ' + name, flush=True)
                    with tempfile.TemporaryDirectory() as directory:
                        row = sample(name, Path(directory) / 'points.bin')
                    result['collection'][name].append(row)
                    if not row['valid']:
                        raise RuntimeError('incomplete collection: ' + name)
            corpus_hashes = {row['sortedCorpusSha256'] for rows in result['collection'].values() for row in rows}
            if len(corpus_hashes) != 1:
                raise RuntimeError('collection corpora differ across modes or repetitions')
            result['collectionSummary'] = {name: summarizeSamples(rows) for name, rows in result['collection'].items()}
        result['valid'] = True
    except Exception as exc:
        result['error'] = str(exc)
    out = Path('/data/packed-polystate-timed', str(time.time_ns()) + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    result['remoteArtifact'] = str(out)
    out.write_text(json.dumps(result, indent=2) + '\n')
    volume.commit()
    return result


@app.local_entrypoint()
def main(output: str = "build/polystate-comparison.json"):
    manifest = source_identity(SOURCE)
    result = run.remote(manifest)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result.get(k) for k in ('valid', 'error', 'screenWinner', 'remoteArtifact')}), flush=True)
    print(f"Comparison saved to {destination}", flush=True)
    if not result['valid']:
        raise RuntimeError(result.get('error', 'comparison failed'))
