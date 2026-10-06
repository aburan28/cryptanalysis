"""Measure hardware ceilings for the ECC2K-130 budget model on one RTX PRO 6000.

    /path/to/modal run run.py

Builds probe.cu with CUDA 13.0 in the image (no GPU needed to compile), runs it
once on a single RTX PRO 6000 allocation and writes result.json next to this
file.  The probe verifies every arithmetic chain on the host, so any number it
prints was produced by instructions that really executed.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import modal

HERE = Path(__file__).parent
app = modal.App('ecc2k130-hardware-limits')
image = (modal.Image.from_registry('nvidia/cuda:13.0.0-devel-ubuntu24.04', add_python='3.12')
         .entrypoint([])
         .apt_install('build-essential')
         .add_local_file(HERE / 'probe.cu', '/root/probe.cu', copy=True)
         .run_commands('nvcc --version',
                       'cd /root && nvcc -O3 -std=c++17 -arch=sm_120 -Xptxas -v probe.cu -o probe 2> ptxas.log; cat ptxas.log'))


@app.function(image=image, gpu='RTX-PRO-6000', timeout=1500)
def run():
    def sh(cmd, timeout=1200):
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return dict(command=cmd, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    result = dict(kind='hardware ceilings; not walk throughput',
                  nvidiaSmi=sh('nvidia-smi --query-gpu=name,uuid,driver_version,clocks.max.sm,clocks.max.memory,power.limit --format=csv'),
                  nvcc=sh('nvcc --version'),
                  ptxas=Path('/root/ptxas.log').read_text(),
                  probeSha256=hashlib.sha256(Path('/root/probe.cu').read_bytes()).hexdigest())
    probe = sh('cd /root && ./probe')
    result['probe'] = probe
    rows = []
    for line in probe['stdout'].splitlines():
        line = line.strip()
        if line.startswith('{'):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    result['rows'] = rows
    result['clocksAfter'] = sh('nvidia-smi --query-gpu=clocks.current.sm,clocks.current.memory,temperature.gpu,power.draw --format=csv')
    return result


@app.local_entrypoint()
def main():
    r = run.remote()
    out = HERE / 'result.json'
    out.write_text(json.dumps(r, indent=1) + '\n')
    print('probe return code', r['probe']['returncode'])
    print(r['probe']['stderr'][-2000:])
    kinds = {}
    for row in r['rows']:
        kinds.setdefault(row.get('kind'), []).append(row)
    for row in kinds.get('device', []):
        print('device', row)
    import statistics
    def med(vals):
        return statistics.median(vals) if vals else float('nan')
    by = {}
    for row in kinds.get('alu', []):
        by.setdefault(row['op'], []).append(row)
    for op, rs in by.items():
        print('%-16s %8.3f T lane-ops/s  %6.1f per SM-clock  clock %5.0f MHz  regs %d resident %d' % (
            op, med([x['teraLaneOpsPerSecond'] for x in rs]), med([x['laneOpsPerSmClock'] for x in rs]),
            med([x['smClockMHzThread0'] for x in rs]), rs[0]['registers'], rs[0]['residentBlocks']))
    by = {}
    for row in kinds.get('loads', []):
        by.setdefault(row['op'], []).append(row)
    for op, rs in by.items():
        print('%-16s %8.3f T lane-loads/s %6.1f per SM-clock  clock %5.0f MHz' % (
            op, med([x['teraLaneLoadsPerSecond'] for x in rs]), med([x['laneLoadsPerSmClock'] for x in rs]),
            med([x['smClockMHzThread0'] for x in rs])))
    by = {}
    for row in kinds.get('bandwidth', []):
        by.setdefault((row['region'], row['mode']), []).append(row)
    for key, rs in by.items():
        print('%-20s %-6s %9.1f GB/s' % (key[0], key[1], med([x['gigabytesPerSecond'] for x in rs])))
    print('wrote', out)
    if r['probe']['returncode'] != 0:
        raise SystemExit('probe failed')
