"""Counted exact roots of S3(x,y,z) over odd-degree binary fields."""

class Counted:
    def __init__(self, field):
        self.f = field
        self.calls = dict.fromkeys(("mul", "sqr", "inv", "frob", "trace", "s3"), 0)

    def mul(self, a, b):
        self.calls["mul"] += 1
        return self.f.mul(a, b)

    def sqr(self, a):
        self.calls["sqr"] += 1
        return self.f.sqr(a)

    def inv(self, a):
        self.calls["inv"] += 1
        return self.f.inv(a)

    def frob(self, a, k):
        self.calls["frob"] += 1
        return self.f.frob(a, k)

    def trace(self, a):
        self.calls["trace"] += 1
        return self.f.trace(a)


def roots(ctx, x, y):
    """Solve (x+y)^2 z^2 + xy z + (xy)^2 + 1 = 0."""
    ctx.calls["s3"] += 1
    f = ctx.f
    a = ctx.sqr(f.add(x, y))
    p = ctx.mul(x, y)
    ps = ctx.sqr(p)
    c = f.add(ps, f.one())
    if a == 0:
        return () if p == 0 else (ctx.mul(c, ctx.inv(p)),)
    if ps == 0:
        return (ctx.frob(ctx.inv(a), f.m - 1),)
    inverse = ctx.inv(ctx.mul(a, ps))
    q = ctx.mul(p, ctx.mul(ps, inverse))
    d = ctx.mul(ctx.mul(c, a), ctx.mul(a, inverse))
    if ctx.trace(d):
        return ()
    half_trace = 0
    value = d
    for _ in range((f.m + 1) // 2):
        half_trace = f.add(half_trace, value)
        value = ctx.frob(value, 2)
    first = ctx.mul(q, half_trace)
    second = f.add(first, q)
    return (first, second) if first != second else (first,)
