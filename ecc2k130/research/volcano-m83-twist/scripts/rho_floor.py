"""Pollard rho over the 53-bit (a2 = 1) conductor-6473 floor: one representative per Frobenius orbit.
Plan frozen in PROTOCOL.md (addendum 2026-10-16).  Resumable; output outputs/rho-floor-a1.jsonl."""
import json, multiprocessing as mp
import twist
from rho_panel import run, N53

SEEDS = (1000, 1001)


def job(arg):
    cid, b, seed = arg
    row = run(b, 1, seed)
    row.update(curve_id=cid, seed=seed, S=row['steps'] / N53 ** 0.5)
    return row


def main():
    inv = twist.load_inventory()
    reps = [r for r in inv if r['curve_id'].endswith('-00') and r['curve_id'] != 'E0']
    assert len(reps) == 78, len(reps)
    path = twist.OUT / 'rho-floor-a1.jsonl'
    done = set()
    if path.exists():
        done = {(d['curve_id'], d['seed']) for d in map(json.loads, path.read_text().splitlines())}
    jobs = [(r['curve_id'], r['b'], s) for s in SEEDS for r in reps if (r['curve_id'], s) not in done]
    with open(path, 'a') as f, mp.Pool(4) as pool:
        for n, row in enumerate(pool.imap_unordered(job, jobs)):
            f.write(json.dumps(row) + '\n'); f.flush()
            print(n, len(jobs), row['curve_id'], row['seed'], row['steps'], round(row['S'], 4), row['wall_s'], flush=True)


if __name__ == '__main__':
    main()
