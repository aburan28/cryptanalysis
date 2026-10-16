"""{±P} Pollard rho on every 53-bit (a2 = 1) conductor-6473 floor curve, one solve each (PROTOCOL.md addendum 2).
    python3 rho_floor_all.py --shard I --of K [--workers W]
Curves are assigned round-robin by inventory index; output outputs/rho-floor-all-a1.shard<I>.jsonl, resumable."""
import argparse, json, multiprocessing as mp
import twist
from rho_panel import run, N53

SEED = 2000


def job(arg):
    cid, b = arg
    row = run(b, 1, SEED)
    row.update(curve_id=cid, seed=SEED, S=row['steps'] / N53 ** 0.5)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', type=int, default=0); ap.add_argument('--of', type=int, default=1)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    floor = [r for r in twist.load_inventory() if r['curve_id'] != 'E0']
    assert len(floor) == 6474
    mine = [r for i, r in enumerate(floor) if i % a.of == a.shard]
    path = twist.OUT / ('rho-floor-all-a1.shard%d.jsonl' % a.shard)
    done = set()
    if path.exists():
        done = {json.loads(l)['curve_id'] for l in path.read_text().splitlines() if l}
    jobs = [(r['curve_id'], r['b']) for r in mine if r['curve_id'] not in done]
    with open(path, 'a') as f, mp.Pool(a.workers) as pool:
        for n, row in enumerate(pool.imap_unordered(job, jobs)):
            f.write(json.dumps(row) + '\n'); f.flush()
            print(n, len(jobs), row['curve_id'], row['steps'], round(row['S'], 4), row['wall_s'], flush=True)


if __name__ == '__main__':
    main()
