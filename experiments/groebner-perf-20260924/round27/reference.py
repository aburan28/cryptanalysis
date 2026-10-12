"""Independent Python oracle: direct specialization and descending row pivots."""
from collections import Counter


def evaluate(items, assignment):
    value = 0
    for mask, coefficient in items:
        if mask & assignment == mask:
            value ^= coefficient
    return value


def full_roots(nvars, items):
    if nvars > 20:
        raise ValueError('reference enumeration bound')
    return [a for a in range(1 << nvars) if evaluate(items,a)==0]


def branch_counts(x, y, equations, items):
    """No producer layout, Gray code, roots, pivots or native arithmetic."""
    if any(type(v) is not int for v in (x,y,equations)) or not (
            1<=x<=20 and y>=1 and x+y<=63 and 1<=equations<=128):
        raise ValueError('reference dimensions')
    items = list(items)
    for mask, coefficient in items:
        if type(mask) is not int or not 0<=mask<1<<(x+y):
            raise ValueError('reference mask')
        if type(coefficient) is not int or not 0<=coefficient<1<<equations:
            raise ValueError('reference coefficient')
        if coefficient and ((mask&((1<<x)-1)).bit_count()>1 or (mask>>x).bit_count()>1):
            raise ValueError('reference nonlinear block')
    total, histogram = 0, Counter()
    for assignment in range(1<<x):
        # Reconstruct residual ANF first. Each term is constant or one y bit.
        residual = {}
        for mask, coefficient in items:
            left, right = mask&((1<<x)-1), mask>>x
            if left & assignment == left:
                residual[right] = residual.get(right,0)^coefficient
        rows = [sum(((c>>i)&1)*(m if m else 1<<y)
                    for m,c in residual.items()) for i in range(equations)]
        # Descending variable columns, pivot search and row swapping.
        rank = 0
        for column in reversed(range(y)):
            pivot = next((j for j in range(rank,equations) if rows[j]>>column&1), None)
            if pivot is None:
                continue
            rows[rank],rows[pivot] = rows[pivot],rows[rank]
            for j in range(rank+1,equations):
                if rows[j]>>column&1:
                    rows[j] ^= rows[rank]
            rank += 1
        consistent = all(row != 1<<y for row in rows)
        histogram[('consistent' if consistent else 'inconsistent',rank)] += 1
        if consistent:
            total += 1<<(y-rank)
    return {'root_count': total, 'branches': 1<<x,
            'histogram': [{'status': status,'rank': rank,'branches': count}
                          for (status,rank),count in sorted(histogram.items())]}


def verify_basis(nvars, items, roots, basis, exact_count):
    if roots != sorted(set(roots)) or len(roots)!=exact_count:
        return False
    if any(type(r) is not int or not 0<=r<1<<nvars or evaluate(items,r) for r in roots):
        return False
    if any(not row or row!=sorted(set(row)) or
           any(type(m) is not int or not 0<=m<1<<nvars for m in row) for row in basis):
        return False
    if any(sum((m&r)==m for m in row)%2 for row in basis for r in roots):
        return False
    leading = [max(row,key=lambda m:(m.bit_count(),-m)) for row in basis]
    if any(i!=j and a&b==b for i,a in enumerate(leading) for j,b in enumerate(leading)):
        return False
    if any(m!=leading[i] and any(m&lm==lm for lm in leading)
           for i,row in enumerate(basis) for m in row):
        return False
    # Set frontier with arbitrary-parent deduplication, unlike native traversal.
    seen, pending, count = set(), [0], 0
    while pending:
        m = pending.pop()
        if m in seen:
            continue
        seen.add(m)
        if any(m&lm==lm for lm in leading):
            continue
        count += 1
        if count>exact_count:
            return False
        for j in range(nvars):
            pending.append(m | (1<<j))
    return count==exact_count
