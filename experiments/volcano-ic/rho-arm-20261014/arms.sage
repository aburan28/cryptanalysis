# Matched signed-Frobenius rho arm for the n = 19 tau-invariant factor-base
# experiment (README "E0 with a tau-invariant factor base").
#
#   sage arms.sage selftest            Sage vs pure-Python rho backends agree; 1-scalar rho check
#   sage arms.sage run [--only-instance I] [--out DIR]
#                                      the frozen protocol: base, tau6 and rho on the ten
#                                      planted scalars, interleaved, one process
#
# Everything about the design is in protocol.json; this file only executes it.
# The IC arms are the unmodified ../ic.sage solveDlp and ../tau.sage tauDlp.

import hashlib
import json
import os
import platform
import random
import sys
import time

MYDIR = os.path.dirname(os.path.abspath(sys.argv[0]))
PARENT = os.path.dirname(MYDIR)

# Load run.sage for MODULUS, ORDER, COFACTOR, scalars() and generator(). It
# derives its directory from sys.argv[0] and dispatches on sys.argv[1], so
# both are swapped out while it loads.
_argv = sys.argv
sys.argv = [os.path.join(PARENT, 'run.sage')]
load(os.path.join(PARENT, 'run.sage'))
sys.argv = _argv
load(os.path.join(PARENT, 'tau.sage'))
sys.path.insert(0, MYDIR)
import rho_frob as rf

PROTO_PATH = os.path.join(MYDIR, 'protocol.json')
PROTO = json.load(open(PROTO_PATH))
SOURCES = [os.path.join(PARENT, f) for f in ('run.sage', 'ic.sage', 'tau.sage', 'nbsat.sage')] + \
          [os.path.join(MYDIR, f) for f in ('arms.sage', 'rho_frob.py', 'protocol.json', 'analyze.py')]


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def jplain(o):
    try:
        return int(o) if o == int(o) and not isinstance(o, float) else float(o)
    except (TypeError, ValueError):
        return str(o)


def runtime_info():
    info = {'sage_version': str(version()), 'python': sys.version, 'platform': platform.platform(),
            'machine': platform.machine(), 'nproc': os.cpu_count(),
            'github': {k: os.environ.get(k) for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
                                                      'GITHUB_REF', 'RUNNER_OS', 'RUNNER_NAME', 'IMAGE_REF')},
            'sources_sha256': {os.path.relpath(p, PARENT): sha256(p) for p in SOURCES if os.path.exists(p)},
            'protocol_sha256': sha256(PROTO_PATH)}
    try:
        models = [l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')]
        info['cpu_model'] = sorted(set(models))
        info['logical_cpus_cpuinfo'] = len(models)
    except OSError:
        pass
    for p in ('/sys/fs/cgroup/cpu.max', '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'):
        if os.path.exists(p):
            info['cgroup_' + os.path.basename(p)] = open(p).read().strip()
    try:
        info['affinity'] = sorted(os.sched_getaffinity(0))
    except AttributeError:
        pass
    return info


def setup_rho(curBase, P):
    B = rf.SageBackend(curBase.E)
    lam = int(tauEigen(curBase, P))
    assert lam == rf.frob_eigen(B, P), 'tau eigenvalue disagrees with tau.sage'
    rp = PROTO['rho']
    c0 = time.process_time()
    tables = [rf.WalkTable(B, P, rp['walk_seed_format'] % k, R=rp['R'])
              for k in range(PROTO['arms']['rho']['reps_per_scalar'])]
    return B, lam, tables, time.process_time() - c0


def selftest():
    """Sage backend agrees with the pure-Python backend point by point."""
    fld = Field(N_BITS, MODULUS, K)
    cur = Curve(fld, 0, fld.F(1), ORDER, COFACTOR)
    P = generator(cur, 'E0')
    ss = scalars()
    assert [int(s) for s in ss] == PROTO['scalars'], 'planted scalars differ from protocol.json'
    B, lam, tables, _ = setup_rho(cur, P)
    Py = rf.PyBackend()
    toPy = lambda T: (B.enc(T[0]), B.enc(T[1]))
    Pp = toPy(P)
    assert Py.on_curve(Pp)
    rng = random.Random('selftest')
    for _ in range(200):
        k1, k2 = rng.randrange(1, cur.p), rng.randrange(1, cur.p)
        A, C = int(k1) * P, int(k2) * P
        assert toPy(A + C) == Py.add(toPy(A), toPy(C))
        assert toPy(A + A) == Py.dbl(toPy(A))
        assert toPy(-A) == Py.neg(toPy(A))
        assert toPy(B.frob(A, 5)) == Py.frob(toPy(A), 5)
        cs, cp = B.canon(A), Py.canon(toPy(A))
        assert toPy(cs[0]) == cp[0] and cs[1:] == cp[1:]
    # One scalar, eight reps, both backends: identical walks and logs.
    Q = int(ss[0]) * P
    Qp = toPy(Q)
    ptab = [rf.WalkTable(Py, Pp, PROTO['rho']['walk_seed_format'] % k, R=PROTO['rho']['R']) for k in range(8)]
    out = []
    for k in range(8):
        a = rf.solve(B, P, Q, lam, tables[k])
        b = rf.solve(Py, Pp, Qp, lam, ptab[k])
        assert a['verified'] and a['log'] == int(ss[0]) % cur.p
        for f in ('steps', 'group_ops', 'fruitless', 'restarts', 'log'):
            assert a[f] == b[f], (k, f, a[f], b[f])
        out.append({'rep': k, 'steps': a['steps'], 'group_ops': a['group_ops']})
    print(json.dumps({'selftest': 'ok', 'P': [str(P[0]), str(P[1])], 'lambda': lam, 'reps': out}))


def run(outdir, onlyInstance=None):
    os.makedirs(outdir, exist_ok=True)
    info = runtime_info()
    info['started_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    ss = [int(s) for s in scalars()]
    assert ss == PROTO['scalars'], 'planted scalars differ from protocol.json'
    # Target-independent setup, outside every timed interval.
    s0 = time.process_time()
    fldB = Field(N_BITS, MODULUS, K)
    curB = Curve(fldB, 0, fldB.F(1), ORDER, COFACTOR)
    fldT = TauField(N_BITS, MODULUS, 6)
    curT = TauCurve(fldT, ORDER, COFACTOR)
    PB = generator(curB, 'E0')
    PT = generator(curT, 'E0')
    assert (str(PB[0]), str(PB[1])) == (str(PT[0]), str(PT[1])), 'generators differ between arms'
    B, lam, tables, rhoSetup = setup_rho(curB, PB)
    info['setup_cpu_s'] = {'all': time.process_time() - s0, 'rho_tables': rhoSetup}
    info['rho_tables'] = {'count': len(tables), 'nominal_ops_each': [t.setup_nominal_ops for t in tables]}
    info['P'] = [str(PB[0]), str(PB[1])]
    info['lambda'] = lam
    json.dump(info, open(os.path.join(outdir, 'runtime-info.json'), 'w'), indent=1, default=jplain)
    path = os.path.join(outdir, 'arms.jsonl')
    with open(path, 'a') as out:
        for slot in PROTO['order']['slots']:
            ii, arm = slot['instance'], slot['arm']
            if onlyInstance is not None and ii != onlyInstance:
                continue
            s = ss[ii]
            rec = {'slot': slot['slot'], 'instance': ii, 'arm': arm, 'scalar': s,
                   'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
            w0 = time.perf_counter()
            if arm == 'base':
                Q = s * PB
                st = solveDlp(curB, PB, Q, random.Random(PROTO['arms']['base']['rng_seed'] % ii))
                st['cpu_s'] = st['total_cpu_s']
                st['correct'] = st['recovered'] and st['log'] == s % curB.p
            elif arm == 'tau6':
                Q = s * PT
                st = tauDlp(curT, PT, Q, random.Random(PROTO['arms']['tau6']['rng_seed'] % ii))
                st['cpu_s'] = st['total_cpu_s']
                st['correct'] = st['recovered'] and st['log'] == s % curT.p
            else:
                Q = s * PB
                reps = []
                for k, tb in enumerate(tables):
                    r1 = rf.solve(B, PB, Q, lam, tb)
                    r1['rep'] = k
                    r1['correct'] = bool(r1['verified']) and r1['log'] == s % curB.p
                    reps.append(r1)
                n = len(reps)
                st = {'reps': reps, 'cpu_s': sum(x['cpu_s'] for x in reps) / n,
                      'cpu_s_rep0': reps[0]['cpu_s'],
                      'cpu_s_to_recovery': sum(x['cpu_s_to_recovery'] for x in reps) / n,
                      'wall_s': sum(x['wall_s'] for x in reps) / n,
                      'steps_mean': sum(x['steps'] for x in reps) / n,
                      'group_ops_mean': sum(x['group_ops'] for x in reps) / n,
                      'verified_reps': sum(1 for x in reps if x['correct']),
                      'correct': all(x['correct'] for x in reps)}
            rec['slot_wall_s'] = time.perf_counter() - w0
            rec.update(st)
            out.write(json.dumps(rec, default=jplain) + '\n')
            out.flush()
            print('slot %2d  scalar %d  %-4s  correct=%s  cpu %.3f s' % (slot['slot'], ii, arm, rec['correct'],
                                                                       rec['cpu_s']), flush=True)
    info['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    json.dump(info, open(os.path.join(outdir, 'runtime-info.json'), 'w'), indent=1, default=jplain)


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] not in ('selftest', 'run'):
        raise SystemExit('usage: sage arms.sage selftest | run [--only-instance I] [--out DIR]')
    if args[0] == 'selftest':
        selftest()
    else:
        out = os.path.join(MYDIR, 'results')
        only = None
        if '--out' in args:
            out = args[args.index('--out') + 1]
        if '--only-instance' in args:
            only = int(args[args.index('--only-instance') + 1])
        run(out, only)
