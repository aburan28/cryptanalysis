"""Bounded RTX PRO 6000 profiler controls, independent of the ECC client image.

Run: modal run profile_diagnostic.py
Builds on CPU, then uses one GPU allocation for normal CUDA and three profiler
controls. Does not change host permissions, driver settings or security modes.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import modal

REMOTE = '/root/profile-diagnostic'
LOCAL = Path(__file__).parent
sys.path.insert(0, str(LOCAL if modal.is_local() else Path(REMOTE)))
from codegen.profilereport import NCU_BINARY, NCU_PACKAGE, profilerVersionError, profileResult

app = modal.App('ecc2k130-profile-diagnostic')
image = (
    modal.Image.from_registry('nvidia/cuda:12.8.1-devel-ubuntu24.04', add_python='3.12')
    .entrypoint([])
    .apt_install(NCU_PACKAGE)
    .add_local_file(LOCAL / 'src/profile_probe.cu', f'{REMOTE}/profile_probe.cu', copy=True)
    .add_local_file(LOCAL / 'codegen/profilereport.py', f'{REMOTE}/codegen/profilereport.py', copy=True)
    .run_commands(f'nvcc -O2 -lineinfo -arch=sm_120 {REMOTE}/profile_probe.cu -o {REMOTE}/probe',
                  f'{NCU_BINARY} --version')
)


def runCommand(command, timeout=45):
    # Bound the whole command tree if ncu or its target stops responding.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    timedOut = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timedOut = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
    return dict(command=command, returncode=process.returncode, output=output, timedOut=timedOut)


def classifyProbe(record):
    if record['timedOut']:
        return dict(available=False, kind='timeout', why='the profiler control timed out',
                    returncode=record['returncode'], log=record['output'])
    return profileResult(record['returncode'], record['output'])


def readEvidence(path, prefixes):
    try:
        lines = Path(path).read_text().splitlines()
        return '\n'.join(line for line in lines if any(p in line for p in prefixes))
    except OSError as error:
        return str(error)


@app.function(image=image, gpu='RTX-PRO-6000', timeout=300)
def diagnose():
    version = runCommand([NCU_BINARY, '--version'])
    info = dict(
        gpu=runCommand(['nvidia-smi', '--query-gpu=name,uuid,driver_version,compute_cap',
                        '--format=csv']),
        profiler=version,
        process=readEvidence('/proc/self/status', ('Uid:', 'CapEff:', 'Seccomp:')),
        driver=readEvidence('/proc/driver/nvidia/params', ('Profiling', 'Debug')),
        deviceNodes=sorted(str(p) for p in Path('/dev').glob('nvidia*')),
    )
    versionError = profilerVersionError(version['output'])
    if version['returncode'] or version['timedOut'] or versionError:
        return dict(info, outcome='profiler_unavailable', why=versionError or version['output'])
    binary = f'{REMOTE}/probe'
    normal = runCommand([binary])
    info['normal'] = normal
    if normal['returncode'] or normal['timedOut'] or 'PROBE PASS' not in normal['output']:
        return dict(info, outcome='normal_cuda_failed')
    cases = []
    settings = (
        ('launch_metadata', ['--section', 'LaunchStats']),
        ('hardware_counters', ['--section', 'SpeedOfLight']),
        ('application_replay', ['--section', 'SpeedOfLight', '--replay-mode', 'application',
                                '--clock-control', 'none', '--cache-control', 'none']),
    )
    for name, flags in settings:
        command = [NCU_BINARY, '--kernel-name', 'probeKernel', '--launch-count', '1'] + flags + [binary]
        record = runCommand(command)
        record.update(name=name, profile=classifyProbe(record))
        cases.append(record)
        print(f'{name}: {record["profile"]["kind"]} (exit {record["returncode"]})', flush=True)
    info['cases'] = cases
    available = [case['name'] for case in cases if case['profile']['available']]
    info['outcome'] = 'some_controls_profiled' if available else 'all_profiler_controls_failed'
    info['availableControls'] = available
    return info


@app.local_entrypoint()
def main(output: str = 'profile-diagnostic.json'):
    result = diagnose.remote()
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    print(f'Diagnostic evidence saved to {output}')
    # Zero means at least one profiling control succeeded, not an ECC result.
    if not result.get('availableControls'):
        raise SystemExit(1)
