"""Floor census and field-representation screen (see PROTOCOL.md).

    python3 census.py floor --a2 1          -> outputs/floor-a1.jsonl
    python3 census.py reps  --a2 1          -> outputs/reps-a1.jsonl
Resumable: rows already in the output file are skipped.
"""
import argparse, hashlib, json, math, multiprocessing as mp, time
import twist

K, S = 12, 1856


def measure(job):
    a2, cid, b, basis, extra = job
    t0 = time.perf_counter()
    rows, meta = twist.tags(a2, b, basis)
    tag = dict(rows)
    nat = twist.count(a2, [t for _, t in rows])
    order = twist.sha_order(list(tag))
    mat = twist.count(a2, [tag[m] for m in order[:S]]) if len(order) >= S else None
    h = twist.CURVES[a2]['h']
    out = dict(curve_id=cid, a2=a2, b=str(b), k=K, x_count=len(rows), eligible=nat,
               matched_size=S, matched_eligible=mat,
               Y_matched=None if mat is None else mat / (16 * math.comb(S, 4) / h),
               Y_natural=nat / (16 * math.comb(len(rows), 4) / h),
               tag_hist_mod2=sum(t & 1 for _, t in rows),
               order_checks=meta['order_checks'], group_ops=meta['group_ops'],
               seconds=round(time.perf_counter() - t0, 3), **extra)
    return out


def rep_rho(i):
    return int.from_bytes(hashlib.sha256(b'volcano-m83-twist-rep:%d' % i).digest(), 'big') >> (256 - 83)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['floor', 'reps'])
    ap.add_argument('--a2', type=int, choices=[0, 1], required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--reps', type=int, default=200)
    args = ap.parse_args()
    path = twist.OUT / ('%s-a%d.jsonl' % (args.mode, args.a2))
    done = set()
    if path.exists():
        done = {json.loads(l)['curve_id'] for l in path.read_text().splitlines() if l}
    if args.mode == 'floor':
        jobs = [(args.a2, r['curve_id'], r['b'], twist.polynomial_basis(K), {})
                for r in twist.load_inventory() if r['curve_id'] not in done]
    else:
        jobs = []
        for i in range(args.reps):
            cid = 'E0-rep%03d' % i
            if cid in done: continue
            rho = twist.FIELD.red(rep_rho(i))
            jobs.append((args.a2, cid, 1, twist.power_basis(rho, K), {'rep': i, 'rho': str(rho)}))
    twist.OUT.mkdir(exist_ok=True)
    with open(path, 'a') as f, mp.Pool(args.workers) as pool:
        for n, row in enumerate(pool.imap_unordered(measure, jobs, chunksize=4)):
            f.write(json.dumps(row) + '\n'); f.flush()
            if n % 500 == 0: print(n, len(jobs), row['curve_id'], row['Y_matched'], flush=True)


if __name__ == '__main__':
    main()
