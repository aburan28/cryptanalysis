"""Control-versus-candidate comparison of ECC_PACKED_ADD_COMBINE on one RTX PRO 6000.

    /path/to/modal run compare.py

Builds the audited RTX PRO 6000 preset twice from this checkout, with the knob
off (control, byte-identical to production) and on (candidate), together with
the GPU arithmetic test and the field-multiplication component probe for each.
The image build also disassembles both clients so the instruction mix of the
walk kernel is recorded. On the GPU: both arithmetic tests must pass, then the
component probe runs control/candidate/control, then complete walk benchmarks
alternate control and candidate (three pairs after one excluded warm-up), each
201,863,462,912 scalar updates at the preset geometry. Writes result.json.
"""
import json
import re
import statistics
import subprocess
from pathlib import Path

import modal

HERE = Path(__file__).parent
ROOT = HERE.parent.parent          # the ecc2k130 checkout
REMOTE = '/root/ecc2k130'
GENCODE = '-gencode arch=compute_120,code=sm_120'
KNOBS = ('BATCH=32 THREADS=256 MINBLOCKS=2 STREAM_KARAT=0 SMEM_SPILL=0 GLOBAL_CG=0 '
         'PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3 '
         'PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 '
         'PACKED_DIRECT_REDUCE=1')
DEFS = ('-DECC_BATCH=32 -DECC_THREADS=256 -DECC_MINBLOCKS=2 -DECC_STREAM_KARAT=0 -DECC_SMEM_SPILL=0 '
        '-DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_CACHE_DENOM=1 -DECC_PACKED_BY_VALUE=1 '
        '-DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_POLY_CHAIN=1 -DECC_PACKED_UNROLL_INV=1 '
        '-DECC_PACKED_PAIR_PRODUCTS=1 -DECC_PACKED_POLY_STATE=1 -DECC_PACKED_DIRECT_REDUCE=1')
MODES = ('0', '1')
WORKERS = 192512
EXPECTED_UPDATES = WORKERS * 32 * 1024 * 32

buildCommands = ['nvcc --version']
for mode in MODES:
    buildCommands += [
        f'cd {REMOTE} && (make -B gpu ARCH="{GENCODE}" {KNOBS} PACKED_ADD_COMBINE={mode} > /root/build-{mode}.log 2>&1 || (cat /root/build-{mode}.log; exit 1))',
        f'cp {REMOTE}/ecc2k130 /root/client-{mode}',
        f'cd {REMOTE} && nvcc -O3 -std=c++17 {GENCODE} {DEFS} -DECC_PACKED_ADD_COMBINE={mode} src/testpackedcuda.cu -o /root/test-{mode}',
        f'cd {REMOTE} && nvcc -O3 -std=c++17 {GENCODE} {DEFS} -DECC_PACKED_ADD_COMBINE={mode} /root/probe/multiplication_probe.cu -o /root/mulprobe-{mode}',
        f'cuobjdump -sass /root/client-{mode} > /root/sass-{mode}.txt',
    ]

app = modal.App('ecc2k130-add-combine')
image = (modal.Image.from_registry('nvidia/cuda:13.0.0-devel-ubuntu24.04', add_python='3.12')
         .entrypoint([])
         .apt_install('build-essential')
         .add_local_dir(ROOT, remote_path=REMOTE, copy=True,
                        ignore=['ecc2k130-cpu', 'ecc2k130', 'build/*', '__pycache__', '*.pyc', 'aws/*',
                                'benchmarks/*', '.claude/*'])
         .add_local_file(HERE / 'multiplication_probe.cu', '/root/probe/multiplication_probe.cu', copy=True)
         .run_commands(*buildCommands))


def sh(cmd, timeout):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return dict(command=cmd, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def walkMix(path):
    """Opcode histogram of the walk kernel (helpers are embedded in its section)."""
    text = Path(path).read_text()
    section = text.split('Function : ')[1] if 'Function : ' in text else text
    section = section.split('Function : ')[0]
    ops = {}
    for line in section.splitlines():
        m = re.match(r'\s*/\*[0-9a-f]+\*/\s+(?:@!?U?P\w+\s+)?([A-Z][A-Z0-9_.]*)', line)
        if m:
            op = m.group(1)
            ops[op] = ops.get(op, 0) + 1
    fam = {}
    for op, n in ops.items():
        key = ('LOP3' if op.startswith('LOP3') else 'IADD3' if op.startswith('IADD3') else
               'IMAD.IADD' if op.startswith('IMAD.IADD') else 'IMAD.WIDE' if op.startswith('IMAD.WIDE') else
               'IMAD.SHL' if op.startswith('IMAD.SHL') else 'IMAD' if op.startswith('IMAD') else
               'SHF' if op.startswith('SHF') else 'IADD' if op.startswith('IADD') else op.split('.')[0])
        fam[key] = fam.get(key, 0) + n
    luts = {}
    for m in re.finditer(r'LOP3\.LUT[^;]*?(0x[0-9a-f]+),\s*!?PT\s*;', section):
        luts[m.group(1)] = luts.get(m.group(1), 0) + 1
    return dict(instructions=sum(ops.values()), families=dict(sorted(fam.items(), key=lambda kv: -kv[1])),
                lop3Luts=dict(sorted(luts.items(), key=lambda kv: -kv[1])))


def resources(mode):
    log = Path(f'/root/build-{mode}.log').read_text()
    walk = re.search(r"Compiling entry function '(\S*walk\S*)'.*?Used (\d+) registers.*?(?=Compiling entry|\Z)", log, re.S)
    spill = re.findall(r'(\d+) bytes spill stores, (\d+) bytes spill loads', log)
    stack = re.findall(r'(\d+) bytes stack frame', log)
    return dict(log=log[-4000:], walkRegisters=int(walk.group(2)) if walk else None,
                spillPairs=spill, stackFrames=stack)


@app.function(image=image, gpu='RTX-PRO-6000', timeout=3600)
def run():
    result = dict(kind='ECC_PACKED_ADD_COMBINE control/candidate comparison; complete scalar walk updates',
                  gpu=sh('nvidia-smi --query-gpu=name,uuid,driver_version,clocks.max.sm,power.limit --format=csv', 60),
                  nvcc=sh('nvcc --version', 60),
                  expectedUpdates=EXPECTED_UPDATES, workers=WORKERS,
                  mix={m: walkMix(f'/root/sass-{m}.txt') for m in MODES},
                  resources={m: resources(m) for m in MODES},
                  arithmetic={}, component=[], walks=[])
    for m in MODES:
        t = sh(f'/root/test-{m}', 600)
        result['arithmetic'][m] = t
        print('arithmetic', m, t['returncode'], t['stdout'][-600:], t['stderr'][-600:], flush=True)
        if t['returncode'] != 0 or 'PASS' not in t['stdout']:
            result['valid'] = False
            return result
    for m in ('0', '1', '0'):
        p = sh(f'/root/mulprobe-{m}', 900)
        rows = [json.loads(l) for l in p['stdout'].splitlines() if l.startswith('{')]
        result['component'].append(dict(mode=m, returncode=p['returncode'], rows=rows, stdout=p['stdout'][-3000:], stderr=p['stderr'][-1000:]))
        print('component', m, p['returncode'], flush=True)
    order = [('0', True), ('0', False), ('1', False), ('0', False), ('1', False), ('0', False), ('1', False)]
    for m, warmup in order:
        cmd = f'/root/client-{m} --curve 131 --packed --bench --steps 1024 --launches 32 --verify 0 --threads {WORKERS}'
        p = sh(cmd, 900)
        out = p['stdout']
        rate = re.findall(r'^\s*finished:\s+(\S+) M it/s,', out, re.M)
        iters = re.findall(r'M it/s\s+(\d+) iterations', out)
        identity = re.findall(r'packed add combine: (\d)', out)
        row = dict(mode=m, warmup=warmup, returncode=p['returncode'],
                   rateMPerSecond=float(rate[0]) if len(rate) == 1 else None,
                   completedUpdates=int(iters[-1]) if iters else None,
                   addCombineIdentity=identity[0] if identity else None,
                   stdout=out[-2500:], stderr=p['stderr'][-1000:])
        row['valid'] = (p['returncode'] == 0 and row['rateMPerSecond'] is not None and row['completedUpdates'] == EXPECTED_UPDATES
                        and row['addCombineIdentity'] == m and 'MISMATCH' not in out and 'stopping:' not in out)
        result['walks'].append(row)
        print('walk', m, 'warmup' if warmup else 'timed', row['rateMPerSecond'], row['completedUpdates'], row['valid'], flush=True)
    result['valid'] = all(r['valid'] for r in result['walks'])
    return result


@app.local_entrypoint()
def main():
    r = run.remote()
    out = HERE / 'result.json'
    out.write_text(json.dumps(r, indent=1) + '\n')
    print('valid', r.get('valid'))
    for m in MODES:
        mix = r['mix'][m]
        print('mode', m, 'walk instructions', mix['instructions'], 'registers', r['resources'][m]['walkRegisters'],
              'spills', r['resources'][m]['spillPairs'][:2])
        print('   families', {k: v for k, v in list(mix['families'].items())[:8]})
        print('   luts', {k: v for k, v in list(mix['lop3Luts'].items())[:8]})
    for c in r['component']:
        by = {}
        for row in c['rows']:
            by.setdefault(row['mode'], []).append(row['billionMultiplicationsPerSecond'])
        print('component mode', c['mode'], {k: round(statistics.median(v), 3) for k, v in by.items()})
    timed = [w for w in r['walks'] if not w['warmup']]
    for m in MODES:
        rates = [w['rateMPerSecond'] for w in timed if w['mode'] == m and w['valid']]
        print('walk mode', m, 'rates', rates, 'median', statistics.median(rates) if rates else None)
    c = [w['rateMPerSecond'] for w in timed if w['mode'] == '0' and w['valid']]
    a = [w['rateMPerSecond'] for w in timed if w['mode'] == '1' and w['valid']]
    if c and a and len(c) == len(a):
        print('paired differences (candidate - control) in %:', [round(100 * (y - x) / x, 3) for x, y in zip(c, a)])
        print('median change: %.3f%%' % (100 * (statistics.median(a) - statistics.median(c)) / statistics.median(c)))
    print('wrote', out)
    if not r.get('valid'):
        raise SystemExit('comparison invalid')
