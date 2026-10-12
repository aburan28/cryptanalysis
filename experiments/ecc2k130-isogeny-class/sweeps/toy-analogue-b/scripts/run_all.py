#!/usr/bin/env python3
"""run_all.py -- merge the Sage ground truth, drive toyrho (C) on every planted instance, verify every log.

Methods
  (i)   R mode 0 on the floor curve itself (negation classes)            -- every floor instance (3 per floor curve)
  (ii)  R mode 1 on E0 (negation + tau classes, class size 358)           -- 1000 E0 instances
  (ii') R mode 0 on E0 (negation only), same code, to isolate the tau gain -- first 300 E0 instances
  (iii) T: floor -> E0 transport by the ascending 359-isogeny, then (ii)  -- every floor instance
  timing run: 120 floor instances, (i) and (iii) interleaved in ONE process (paired timing, same conditions)
"""
import json, glob, os, subprocess, sys, hashlib, time
from concurrent.futures import ThreadPoolExecutor

RAW = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/'
BIN = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/scripts/toyrho'
NBT = RAW + 'nb_tables.txt'
WORKERS = int(os.environ.get('WORKERS', '10'))

def seed_of(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)

def merge():
    s1 = json.load(open(RAW + 'stage1.json'))
    curves, inst_floor, inst_E0, tcheck = [], [], [], []
    files = sorted(glob.glob(RAW + 'stage2_*_*.json'), key=lambda p: int(p.split('_')[-2]))
    for p in files:
        d = json.load(open(p))
        curves += d['curves']; inst_floor += d['instances_floor']
        inst_E0 += d.get('instances_E0', []); tcheck += d.get('transport_formula_check', [])
    labels = [c['label'] for c in curves]
    assert labels == [c['label'] for c in s1['curves']], 'stage2 chunks do not cover the 358 curves in order'
    gt = dict(meta=s1['meta'], stage1_log=s1['log'], curves=curves, instances_floor=inst_floor, instances_E0=inst_E0,
              transport_formula_check=tcheck)
    json.dump(gt, open(RAW + 'toy_ground_truth.json', 'w'))
    return gt

def run_lines(lines):
    """run toyrho on a list of command lines, split over WORKERS processes; returns parsed JSON records"""
    chunks = [lines[i::WORKERS] for i in range(WORKERS)]
    def work(ch):
        if not ch: return []
        p = subprocess.run([BIN, NBT], input='\n'.join(ch) + '\n', capture_output=True, text=True, timeout=2400)
        if p.returncode != 0: raise RuntimeError(p.stderr)
        return [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
    out = []
    with ThreadPoolExecutor(WORKERS) as ex:
        for r in ex.map(work, chunks): out += r
    return out

def main():
    gt = merge()
    m = gt['meta']; N = int(m['N']); s = int(m['tau_eigen_s']); cofTw = hex(int(m['cof359_twist']))
    bmap = {c['label']: hex(int(c['b_int'])) for c in gt['curves']}
    kmap = {}
    Li, Lii, Liip, Liii = [], [], [], []
    for x in gt['instances_floor']:
        iid = '%s_%d' % (x['curve'], x['idx']); kmap[iid] = x['k']
        g = '%s %s %s %s' % (x['Gx'], x['Gy'], x['Hx'], x['Hy'])
        Li.append('R %s 0 0x1 %s %d %d %s 16 8 %d' % (iid, bmap[x['curve']], N, s, g, seed_of('i' + iid)))
        Liii.append('T %s %s %s 359 %d %d %s 8 5 %d' % (iid, bmap[x['curve']], cofTw, N, s, g, seed_of('iii' + iid)))
    for x in gt['instances_E0']:
        iid = 'E0_%d' % x['idx']; kmap[iid] = x['k']
        g = '%s %s %s %s' % (x['Gx'], x['Gy'], x['Hx'], x['Hy'])
        Lii.append('R %s 1 0x1 0x1 %d %d %s 8 5 %d' % (iid, N, s, g, seed_of('ii' + iid)))
        if x['idx'] < 300:
            Liip.append('R %s 0 0x1 0x1 %d %d %s 16 8 %d' % (iid, N, s, g, seed_of('iip' + iid)))
    res = {}
    for name, lines in [('ii', Lii), ('iip', Liip), ('i', Li), ('iii', Liii)]:
        t0 = time.time()
        recs = run_lines(lines)
        for r in recs:
            r['planted_k'] = kmap[r['id']]
            r['k_matches_planted'] = (r['found'] == 1 and r['k'] == r['planted_k'])
        res[name] = recs
        bad = [r['id'] for r in recs if not r['k_matches_planted']]
        print(name, len(recs), 'instances;', len(bad), 'mismatches', bad[:5], '%.1f s' % (time.time() - t0), flush=True)
        json.dump(recs, open(RAW + 'results_%s.jsonl' % name, 'w'))
    # paired timing run: one process, (i) and (iii) alternating on 120 floor instances (idx 0 of every 3rd curve)
    sel = [x for x in gt['instances_floor'] if x['idx'] == 0][::3]
    lines = []
    for x in sel:
        iid = '%s_%d' % (x['curve'], x['idx'])
        lines.append([l for l in Li if l.split()[1] == iid][0])
        lines.append([l for l in Liii if l.split()[1] == iid][0])
    p = subprocess.run([BIN, NBT], input='\n'.join(lines) + '\n', capture_output=True, text=True, timeout=2400)
    recs = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
    for r in recs:
        r['planted_k'] = kmap[r['id']]; r['k_matches_planted'] = (r['found'] == 1 and r['k'] == r['planted_k'])
    json.dump(recs, open(RAW + 'results_timing_paired.jsonl', 'w'))
    print('paired timing', len(recs), 'records;', sum(not r['k_matches_planted'] for r in recs), 'mismatches')

if __name__ == '__main__':
    main()
