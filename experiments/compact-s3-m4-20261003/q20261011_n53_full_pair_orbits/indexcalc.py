"""Sparse-checkout adapter for the exact combinationsUpTo base enumeration."""


def combinationsUpTo(n, w):
    """Index subsets of size at most w, smallest first (Q1301 order)."""
    out = [[]]
    cur = [[]]
    for _ in range(w):
        nxt = []
        for subset in cur:
            start = subset[-1] + 1 if subset else 0
            for i in range(start, n):
                nxt.append(subset + [i])
        out.extend(nxt)
        cur = nxt
    return out
