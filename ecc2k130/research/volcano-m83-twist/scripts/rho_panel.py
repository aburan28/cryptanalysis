"""Pollard rho on the a2 = 1 twist (53-bit prime N53), same f83x arithmetic as the yield census.

Frozen plan (written before any rho output was read):
  crater E0 (b = 1): MODE 2 ({+-tau^i P}) x 16 seeds, MODE 1 ({+-P}) x 6, MODE 0 (plain) x 4
  floor O00-00, O39-00, O77-82 (first, middle, last of the inventory): MODE 1 x 3, MODE 0 x 2
  (floor curves are not defined over F_2: no tau, so MODE 2 does not exist there)
Seeds 1000 + i; DP bits 10 (MODE 2) or 14 (MODE 0/1).  One walk per solve, one core.
Yield of rho = collisions per step; reported as S = steps / sqrt(n) against
sqrt(pi/2), sqrt(pi/4) and sqrt(pi/(4*83)).
The a2 = 0 twist (81-bit ELL) needs ~2^37 steps with tau classes: not run, predicted only.
"""
import json, subprocess, time
import twist

N53 = twist.N53
MU = 1                                     # a2 = 1: tau^2 - tau + 2 = 0
PLAN = [('E0', 2, 16), ('E0', 1, 6), ('E0', 0, 4)] + \
       [(c, m, r) for c in ('O00-00', 'O39-00', 'O77-82') for m, r in ((1, 3), (0, 2))]


def tau_eigenvalues(n):
    # roots of l^2 - MU l + 2 mod n (n = 3 mod 4? use Tonelli-Shanks generally)
    a = (MU * MU - 8) % n
    q, s = n - 1, 0
    while q % 2 == 0: q //= 2; s += 1
    z = 2
    while pow(z, (n - 1) // 2, n) != n - 1: z += 1
    m, c, t, r = s, pow(z, q, n), pow(a, q, n), pow(a, (q + 1) // 2, n)
    while t != 1:
        i, tt = 0, t
        while tt != 1: tt = tt * tt % n; i += 1
        b = pow(c, 1 << (m - i - 1), n); m, c, t, r = i, b * b % n, t * b * b % n, r * b % n
    i2 = pow(2, -1, n)
    return [(MU + r) * i2 % n, (MU - r) * i2 % n]


def run(b, mode, seed):
    c = twist.CURVES[1]
    lams = tau_eigenvalues(N53) if mode == 2 else [0]
    for lam in lams:
        t0 = time.perf_counter()
        r = subprocess.run([str(twist.NATIVE), 'rho', '1', '%x' % b, str(c['N']), str(c['h']), str(mode), str(lam),
                            str(seed), '10' if mode == 2 else '14'], capture_output=True, text=True)
        wall = time.perf_counter() - t0
        if r.returncode == 7: continue          # the other eigenvalue
        if r.returncode: raise RuntimeError(r.stderr)
        f = r.stdout.split()
        row = {f[i]: int(f[i + 1]) for i in range(1, len(f) - 1, 2)}
        row.update(lam=lam, wall_s=round(wall, 3))
        return row
    raise RuntimeError('no tau eigenvalue matched')


def main():
    inv = {r['curve_id']: r['b'] for r in twist.load_inventory()}
    path = twist.OUT / 'rho-a1.jsonl'
    done = set()
    if path.exists():
        done = {(d['curve_id'], d['mode'], d['seed']) for d in map(json.loads, path.read_text().splitlines())}
    with open(path, 'a') as f:
        for cid, mode, reps in PLAN:
            for i in range(reps):
                seed = 1000 + i
                if (cid, mode, seed) in done: continue
                row = run(inv[cid], mode, seed)
                row.update(curve_id=cid, seed=seed, S=row['steps'] / N53 ** 0.5)
                f.write(json.dumps(row) + '\n'); f.flush()
                print(cid, mode, seed, row['steps'], round(row['S'], 4), row['wall_s'], flush=True)


if __name__ == '__main__':
    main()
