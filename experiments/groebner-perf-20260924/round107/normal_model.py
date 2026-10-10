"""Native-free quotient map and direct-division work models on exact sets."""

FIELDS = ('mode', 'selected', 'fallback_large_ring', 'fallback_sparse',
          'fallback_dimension', 'fallback_bytes', 'input_terms', 'universe',
          'dimension', 'peak_bytes', 'planning_work', 'table_products',
          'table_terms', 'input_xors', 'work')


def order(monomial):
    return monomial.bit_count(), -monomial


def multiple(row, mask):
    result = set()
    for term in row:
        value = term | mask
        if value in result:
            result.remove(value)
        else:
            result.add(value)
    return result


def reference(n, originals, basis):
    """The original remainder's arithmetic charge, excluding common lead setup."""
    basis = list(map(set, basis))
    leads = [max(row, key=order) for row in basis]
    work = steps = 0
    results = []
    for original in originals:
        value, tail = set(original), set()
        while value:
            work += len(value)
            lead = max(value, key=order)
            for row, divisor in zip(basis, leads):
                work += 1
                if lead & divisor != divisor:
                    continue
                product = multiple(row, lead & ~divisor)
                work += len(row) + len(product)
                assert product and max(product, key=order) == lead
                work += len(value) + len(product)
                value.symmetric_difference_update(product)
                steps += 1
                break
            else:
                tail.add(lead)
                value.remove(lead)
        results.append(tail)
    return dict(work=work, reduction_steps=steps, results=results)


def model(n, originals, basis, *, mode=1, byte_limit=1048576):
    stats = dict.fromkeys(FIELDS, 0)
    stats['mode'] = mode
    if not mode:
        return stats, None
    if n > 12:
        stats['fallback_large_ring'] = 1
        return stats, None
    originals, basis = list(map(set, originals)), list(map(set, basis))
    count = 1 << n
    stats.update(universe=count, input_terms=sum(map(len, originals)), work=len(originals))
    if mode == 1 and stats['input_terms'] < 2*count:
        stats['fallback_sparse'] = 1
        return stats, None
    if count*8 > byte_limit:
        stats['fallback_bytes'] = 1
        return stats, None
    stats['planning_work'] = count*(n+2)
    stats['work'] += stats['planning_work']
    stats['peak_bytes'] = count*8
    leads = [max(row, key=order) for row in basis]
    values = {}
    for monomial in sorted(range(count), key=order):
        for index, lead in enumerate(leads):
            stats['work'] += 1
            if monomial & lead == lead:
                break
        else:
            if stats['dimension'] == 64:
                stats.update(dimension=65, fallback_dimension=1)
                return stats, None
            values[monomial] = 1 << stats['dimension']
            stats['dimension'] += 1
            continue
        product = multiple(basis[index], monomial & ~lead)
        stats['table_products'] += 1
        stats['work'] += len(basis[index]) + len(product)
        assert product and max(product, key=order) == monomial
        product.remove(monomial)
        stats['work'] += len(product)
        stats['table_terms'] += len(product)
        bits = 0
        for term in product:
            assert order(term) < order(monomial)
            bits ^= values[term]
        values[monomial] = bits
    stats['selected'] = 1
    results = []
    for row in originals:
        stats['work'] += len(row)
        value = 0
        for term in row:
            value ^= values[term]
            stats['input_xors'] += 1
        results.append(value)
        if value:
            break
    return stats, results
