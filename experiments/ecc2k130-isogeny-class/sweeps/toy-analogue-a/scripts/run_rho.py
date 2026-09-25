#!/usr/bin/env python3
"""Run the rho solver on every input file of a family in parallel chunks.

usage: python3 run_rho.py <family> [workers] [config-substring ...]
Compiles bin/rho_<family> with the family's field fixed at compile time, splits each
raw/<family>/inputs/<config>.txt into chunks, runs them with a process pool and writes
raw/<family>/out/<config>.tsv (header + one row per instance).
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

WORK = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a'
fam = sys.argv[1]
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
filters = sys.argv[3:]
meta = json.load(open(os.path.join(WORK, 'data', f'{fam}_family.json')))['meta']
binp = os.path.join(WORK, 'bin', f'rho_{fam}')
subprocess.run(['clang', '-O3', '-mcpu=apple-m1', '-Wall', f"-DFIXN={meta['n']}", f"-DFIXTAIL={meta['modulus_tail']}",
                '-o', binp, os.path.join(WORK, 'scripts', 'rho.c')], check=True)
ind = os.path.join(WORK, 'raw', fam, 'inputs')
outd = os.path.join(WORK, 'raw', fam, 'out')
os.makedirs(outd, exist_ok=True)
os.makedirs(os.path.join(WORK, 'raw', fam, 'chunks'), exist_ok=True)
configs = sorted(f[:-4] for f in os.listdir(ind) if f.endswith('.txt'))
if filters:
    configs = [c for c in configs if any(x in c for x in filters)]
jobs = []
for cfg in configs:
    lines = open(os.path.join(ind, cfg + '.txt')).read().splitlines(True)
    hdr = [x for x in lines if not x.startswith('inst ')]
    insts = [x for x in lines if x.startswith('inst ')]
    if not insts:
        continue
    per = max(1, (len(insts) + 4 * workers - 1) // (4 * workers))
    for ci in range(0, len(insts), per):
        cp = os.path.join(WORK, 'raw', fam, 'chunks', f'{cfg}.{ci:05d}')
        with open(cp + '.in', 'w') as fh:
            fh.writelines(hdr + insts[ci:ci + per])
        jobs.append((cfg, cp))


def run(job):
    cfg, cp = job
    with open(cp + '.in') as fi, open(cp + '.out', 'w') as fo, open(cp + '.err', 'w') as fe:
        r = subprocess.run(['timeout', '2400', binp], stdin=fi, stdout=fo, stderr=fe)
    return cfg, cp, r.returncode


t0 = time.time()
rcs = {}
with ThreadPoolExecutor(workers) as ex:
    for cfg, cp, rc in ex.map(run, jobs):
        rcs.setdefault(cfg, []).append(rc)
for cfg in configs:
    chunks = sorted(cp for c, cp in jobs if c == cfg)
    rows, header = [], None
    for cp in chunks:
        ls = open(cp + '.out').read().splitlines()
        if ls:
            header = ls[0]
            rows += ls[1:]
    with open(os.path.join(outd, cfg + '.tsv'), 'w') as fh:
        fh.write((header or '') + '\n' + '\n'.join(rows) + ('\n' if rows else ''))
    bad = [rc for rc in rcs.get(cfg, []) if rc != 0]
    print(f'{fam} {cfg}: {len(rows)} rows, nonzero rc: {bad}', flush=True)
print('elapsed', round(time.time() - t0, 1))
