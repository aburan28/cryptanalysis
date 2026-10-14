#!/usr/bin/env python3
"""Run the frozen packed K900/K1271/K1200 N83 capacity screen once."""

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
BIN = Path(os.environ.get('N83_BIN_DIR',
    '/Volumes/SSD990/llm/tmp/n83-base-size-cargo-target/release/examples'))
TARGET = HERE / 'target.jsonl'
PROTOCOL = HERE / 'protocol.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_json(path, value):
    with path.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write('\n')


def rss_bytes(pid):
    try:
        return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)],
                                           text=True, stderr=subprocess.DEVNULL).strip()) * 1024
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0


def run_arm(name, command, extra_env, cap_s, rss_cap):
    arm = HERE / 'runs' / name
    arm.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.update({'KIC_RANK_THREADS': '12', 'KIC_TARGET_THREADS': '1', 'LC_ALL': 'C'})
    environment.update(extra_env)
    receipt = {'arm': name, 'command': list(map(str, command)),
               'environment_overrides': extra_env,
               'source_commit': json.loads(PROTOCOL.read_text())['source_commit'],
               'binary_sha256': sha(Path(command[0])), 'target_sha256': sha(TARGET),
               'timeout_seconds': cap_s, 'rss_cap_bytes': rss_cap}
    create_json(arm / 'started.json', receipt)
    started = time.monotonic()
    peak = 0
    missing_rss_samples = 0
    disposition = 'exit'
    with (arm / 'stdout.txt').open('xb') as out, (arm / 'stderr.txt').open('xb') as err:
        process = subprocess.Popen(list(map(str, command)), cwd=CRYPTO,
                                   env=environment, stdout=out, stderr=err,
                                   start_new_session=True)
        while process.poll() is None:
            sample = rss_bytes(process.pid)
            missing_rss_samples = missing_rss_samples + 1 if sample == 0 else 0
            peak = max(peak, sample)
            if missing_rss_samples >= 3:
                disposition = 'rss_monitor_failure'
                os.killpg(process.pid, signal.SIGTERM)
                break
            if peak > rss_cap:
                disposition = 'rss_cap'
                os.killpg(process.pid, signal.SIGTERM)
                break
            if time.monotonic() - started > cap_s:
                disposition = 'time_cap'
                os.killpg(process.pid, signal.SIGTERM)
                break
            time.sleep(0.5)
        try:
            code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    receipt.update({'disposition': disposition, 'exit_code': code,
                    'process_wall_s': time.monotonic() - started,
                    'sampled_peak_rss_bytes': peak,
                    'stdout_sha256': sha(arm / 'stdout.txt'),
                    'stderr_sha256': sha(arm / 'stderr.txt')})
    output_file = arm / ('target.jsonl' if name.startswith('K') else 'rho.json')
    if output_file.exists():
        receipt['output_sha256'] = sha(output_file)
    base_file = arm / 'base.jsonl'
    if base_file.exists():
        receipt['base_sha256'] = sha(base_file)
    create_json(arm / 'execution.json', receipt)
    print(json.dumps({'arm': name, 'disposition': disposition, 'exit_code': code,
                      'process_wall_s': receipt['process_wall_s'],
                      'sampled_peak_rss_bytes': peak}), flush=True)


def main():
    protocol = json.loads(PROTOCOL.read_text())
    assert sha(CRYPTO / 'examples/koblitz_orbit_dlp_fast.rs') == protocol['ic_source_sha256']
    assert sha(CRYPTO / 'examples/n83_rho_optimization_eval.rs') == protocol['rho_source_sha256']
    assert sha(CRYPTO / 'Cargo.lock') == protocol['cargo_lock_sha256']
    assert sha(TARGET) == protocol['target_sha256']
    assert sha(HERE / 'validation_sidecar.json') == protocol['validation_sidecar_sha256']
    assert rss_bytes(os.getpid()) > 0, 'process RSS polling is unavailable'
    assert json.loads((HERE / 'rho_config.json').read_text()) == protocol['rho_policy']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CRYPTO, text=True).strip() == protocol['source_commit']
    assert subprocess.check_output(['git', 'status', '--porcelain=v1'],
                                   cwd=CRYPTO, text=True).strip() == '', 'source checkout is dirty'
    ic, rho = BIN / 'koblitz_orbit_dlp_fast', BIN / 'n83_rho_optimization_eval'
    build_environment = os.environ.copy()
    for name in list(build_environment):
        if (name in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_TARGET')
                or name.startswith('CARGO_PROFILE_')):
            build_environment.pop(name)
    build_environment['CARGO_TARGET_DIR'] = str(BIN.parent.parent)
    build = subprocess.run(['cargo', 'build', '--release', '--locked', '--offline',
                            '--example', ic.name, '--example', rho.name],
                           cwd=CRYPTO, env=build_environment,
                           text=True, capture_output=True)
    with (HERE / 'build_stdout.txt').open('x') as out:
        out.write(build.stdout)
    with (HERE / 'build_stderr.txt').open('x') as err:
        err.write(build.stderr)
    assert build.returncode == 0, 'pinned clean-source build failed'
    assert ic.is_file() and rho.is_file()
    create_json(HERE / 'binary_manifest.json', {'ic_sha256': sha(ic), 'rho_sha256': sha(rho),
                                                 'protocol_sha256': sha(PROTOCOL),
                                                 'target_sha256': sha(TARGET)})
    order = protocol['arms']
    assert order == ['rho_before', 'K900', 'K1271', 'K1200', 'rho_after']
    for name in order:
        arm = HERE / 'runs' / name
        if name.startswith('rho'):
            command = [rho, TARGET, str(protocol['rho_seed']), HERE / 'rho_config.json', arm / 'rho.json']
            run_arm(name, command, {}, protocol['rho_process_cap_seconds'], protocol['sampled_rss_cap_bytes'])
        else:
            k = int(name[1:])
            command = [ic, f'construct:83:1:{k}', TARGET, str(protocol['rank_seed']), arm / 'target.jsonl']
            run_arm(name, command, {'KIC_DUMP_BASE': str(arm / 'base.jsonl'),
                                    'KIC_PACKED_ROOT_TABLE': '1'},
                    protocol['ic_process_cap_seconds'], protocol['sampled_rss_cap_bytes'])


if __name__ == '__main__':
    main()
