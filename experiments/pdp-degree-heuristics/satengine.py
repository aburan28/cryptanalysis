"""CryptoMiniSat on the descended system: the ANF -> CNF+XOR route of pdp-scaling/solve.py.

Every monomial of degree >= 2 becomes a Tseitin AND variable and each Boolean equation one
native XOR clause.  pycryptosat reports no conflict counts, so the record is the status
and the process CPU time of the solve call; a time or conflict limit censors the call.
"""

from __future__ import annotations

import time


def solve(system, time_limit: float = 10.0, confl_limit: int | None = None) -> dict:
    try:
        import pycryptosat
    except ImportError:
        return {"status": "unavailable"}
    kw = {"threads": 1, "time_limit": time_limit}
    if confl_limit:
        kw["confl_limit"] = confl_limit
    s = pycryptosat.Solver(**kw)
    nv = system.N
    aux: dict[int, int] = {}
    nxt = nv + 1
    for mask in set(int(a) for a in system.masks):
        if mask & (mask - 1) == 0:
            continue
        lits = [j + 1 for j in range(nv) if (mask >> j) & 1]
        aux[mask] = nxt
        for v in lits:
            s.add_clause([-nxt, v])
        s.add_clause([nxt] + [-v for v in lits])
        nxt += 1
    for eq in system.equations:
        xs, rhs = [], False
        for mask in eq.tolist():
            if mask == 0:
                rhs = not rhs
            elif mask & (mask - 1) == 0:
                xs.append(mask.bit_length())
            else:
                xs.append(aux[mask])
        if xs:
            s.add_xor_clause(xs, rhs)
        elif rhs:
            return {"status": "unsat", "cpu_s": 0.0, "aux_vars": len(aux)}
    t0 = time.process_time()
    sat, model = s.solve()
    cpu = time.process_time() - t0
    if sat is None:
        return {"status": "budget", "cpu_s": cpu, "aux_vars": len(aux)}
    out = {"status": "sat" if sat else "unsat", "cpu_s": cpu, "aux_vars": len(aux)}
    if sat:
        out["assignment"] = sum(1 << j for j in range(nv) if model[j + 1])
    return out
