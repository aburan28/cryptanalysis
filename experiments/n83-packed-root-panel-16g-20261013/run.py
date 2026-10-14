#!/usr/bin/env python3
"""Run the frozen held-out N83 packed-root panel, retaining every arm."""

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-packed-root-crypto-20261013'))
BIN_DIR = Path(os.environ.get('N83_BIN_DIR',
    '/Volumes/SSD990/llm/tmp/n83-base-size-cargo-target/release/examples'))
PROTOCOL = HERE / 'protocol.json'
TARGETS = HERE / 'targets.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write('\n')


def rss_bytes(pid):
    try:
        return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)],
                                           text=True, stderr=subprocess.DEVNULL).strip()) * 1024
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0


def run_arm(name, binary, protocol):
    arm = HERE / 'runs' / name
    arm.mkdir(parents=True, exist_ok=False)
    command = [str(binary), f'construct:83:1:{int(name[1:])}',
               str(TARGETS), str(protocol['rank_seed']), str(arm / 'targets.jsonl')]
    environment = os.environ.copy()
    overrides = {'KIC_RANK_THREADS': str(protocol['rank_threads']),
                 'KIC_TARGET_THREADS': str(protocol['target_threads']),
                 'KIC_PACKED_ROOT_TABLE': '1',
                 'KIC_DUMP_BASE': str(arm / 'base.jsonl'), 'LC_ALL': 'C'}
    environment.update(overrides)
    receipt = {'arm': name, 'command': command, 'environment_overrides': overrides,
               'source_commit': protocol['source_commit'], 'binary_sha256': sha(binary),
               'targets_sha256': sha(TARGETS),
               'timeout_seconds': protocol['ic_process_cap_seconds'],
               'rss_cap_bytes': protocol['sampled_rss_cap_bytes']}
    write_json(arm / 'started.json', receipt)
    began = time.monotonic()
    peak = 0
    missing_samples = 0
    disposition = 'exit'
    with (arm / 'stdout.txt').open('xb') as out, (arm / 'stderr.txt').open('xb') as err:
        process = subprocess.Popen(command, cwd=CRYPTO, env=environment,
                                   stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            sample = rss_bytes(process.pid)
            missing_samples = missing_samples + 1 if sample == 0 else 0
            peak = max(peak, sample)
            if missing_samples >= 3:
                disposition = 'rss_monitor_failure'
            elif peak > protocol['sampled_rss_cap_bytes']:
                disposition = 'rss_cap'
            elif time.monotonic() - began > protocol['ic_process_cap_seconds']:
                disposition = 'time_cap'
            if disposition != 'exit':
                os.killpg(process.pid, signal.SIGTERM)
                break
            time.sleep(protocol['rss_poll_seconds'])
        try:
            exit_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            exit_code = process.wait()
    receipt.update({'disposition': disposition, 'exit_code': exit_code,
                    'process_wall_s': time.monotonic() - began,
                    'sampled_peak_rss_bytes': peak,
                    'stdout_sha256': sha(arm / 'stdout.txt'),
                    'stderr_sha256': sha(arm / 'stderr.txt')})
    for label in ('targets', 'base'):
        output = arm / f'{label}.jsonl'
        if output.exists():
            receipt[f'{label}_output_sha256'] = sha(output)
    write_json(arm / 'execution.json', receipt)
    print(json.dumps({'arm': name, 'disposition': disposition,
                      'exit_code': exit_code, 'process_wall_s': receipt['process_wall_s'],
                      'sampled_peak_rss_bytes': peak}), flush=True)


def main():
    protocol = json.loads(PROTOCOL.read_text())
    assert sha(TARGETS) == protocol['targets_sha256']
    assert sha(HERE / 'validation_sidecar.json') == protocol['validation_sidecar_sha256']
    assert sha(CRYPTO / 'examples/koblitz_orbit_dlp_fast.rs') == protocol['ic_source_sha256']
    assert sha(CRYPTO / 'Cargo.lock') == protocol['cargo_lock_sha256']
    assert sha(CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py') == protocol['arithmetic_source_sha256']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CRYPTO,
                                   text=True).strip() == protocol['source_commit']
    assert subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=CRYPTO,
                                   text=True).strip() == '', 'source checkout is dirty'
    assert rss_bytes(os.getpid()) > 0, 'RSS polling is unavailable'
    assert len(TARGETS.read_text().splitlines()) == protocol['target_count']
    build_environment = os.environ.copy()
    for name in list(build_environment):
        if name in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_TARGET') or name.startswith('CARGO_PROFILE_'):
            build_environment.pop(name)
    build_environment['CARGO_TARGET_DIR'] = str(BIN_DIR.parent.parent)
    build = subprocess.run(['cargo', 'build', '--release', '--locked', '--offline',
                            '--example', 'koblitz_orbit_dlp_fast'],
                           cwd=CRYPTO, env=build_environment, text=True, capture_output=True)
    (HERE / 'build_stdout.txt').write_text(build.stdout)
    (HERE / 'build_stderr.txt').write_text(build.stderr)
    assert build.returncode == 0, 'pinned clean-source build failed'
    binary = BIN_DIR / 'koblitz_orbit_dlp_fast'
    assert binary.is_file()
    write_json(HERE / 'binary_manifest.json',
               {'ic_sha256': sha(binary), 'protocol_sha256': sha(PROTOCOL),
                'targets_sha256': sha(TARGETS), 'source_commit': protocol['source_commit']})
    assert protocol['arms'] == ['K1100', 'K1000', 'K899', 'K900', 'K1271', 'K800', 'K1200']
    for name in protocol['arms']:
        run_arm(name, binary, protocol)


if __name__ == '__main__':
    main()
