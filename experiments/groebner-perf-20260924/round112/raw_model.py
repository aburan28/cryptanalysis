"""Native-free integer-row replay of both producers, including budget prefixes.

Rows are Python integers rather than vectors of native words. Counters model
the declared software charges; they are not estimates of machine instructions.
"""
from itertools import combinations
from block_model import Tables, FIELDS as BLOCK_FIELDS

FIELDS = ('work', 'rows', 'forward_xors', 'backward_xors', 'word_xors', 'pivots',
          'kept_rows', 'nodes', 'output_nodes', 'peak_payload_words', 'status')


class Limit(Exception):
    pass


def monomials(n, degree):
    return [sum(1 << i for i in c) for d in range(degree+1)
            for c in combinations(range(n), d)]


def model(n, rows, degree, multiplier_degree, *, minimal=False, max_work=20000000,
          max_nodes=2000000, max_rows=4096, packed_masks=None, block=False, block_bits=4, table_bytes=4194304, retain_raw=False):
    stats = dict.fromkeys(FIELDS, 0)
    block_stats = dict.fromkeys(BLOCK_FIELDS, 0)
    block_stats['bits'] = block_bits if block else 0
    graph = []
    basis, outputs = [], []

    def charge(amount=1):
        if amount > max_work-stats['work']:
            raise Limit('matrix work budget')
        stats['work'] += amount

    def emit(node):
        if len(graph) >= max_nodes:
            raise Limit('matrix proof node budget')
        graph.append(node)
        stats['nodes'] = len(graph)
        return len(graph)-1

    try:
        support = sorted(monomials(n, degree))
        columns = sorted(monomials(n, min(n, degree+multiplier_degree)),
                         key=lambda m: (-m.bit_count(), m))
        multipliers = monomials(n, multiplier_degree)
        width = (len(columns)+63)//64
        if len(rows)*len(multipliers) > max_rows:
            raise Limit('matrix row budget')
        if width*(min(len(rows)*len(multipliers), len(columns))+1) > 8388608:
            raise Limit('matrix payload budget')
        inputs = []
        for row in rows:
            terms = set()
            for term in row:
                terms.symmetric_difference_update((term,))
            inputs.append(terms)
        masks = sorted(set().union(*inputs)) if packed_masks is None else list(packed_masks)
        assert len(set(masks)) == len(masks) and set(masks) <= set(support)
        assert set().union(*inputs) <= set(masks)
        charge(len(rows))
        charge(len(support))
        for mask in masks:
            charge()
            lo, hi = 0, len(support)
            while lo < hi:
                charge()
                mid = (lo+hi)//2
                if support[mid] < mask:
                    lo = mid+1
                else:
                    hi = mid
            charge()
            charge((len(rows)+63)//64)
            for row in inputs:
                if mask in row:
                    charge()
        for i in range(len(rows)):
            emit(['input', i])
        positions = {m: i for i, m in enumerate(columns)}
        tables = Tables(block_stats, stats, len(columns), width, table_bytes, charge, emit)
        tables.prepare()
        pivots = {}

        def xor(bits, proof, c, backward):
            charge(width-c//64)
            new = emit(['xor', proof, pivots[c][1]])
            stats['word_xors'] += width-c//64
            stats['backward_xors' if backward else 'forward_xors'] += 1
            return bits ^ pivots[c][0], new

        for e, row in enumerate(inputs):
            for multiplier in multipliers:
                charge()
                stats['rows'] += 1
                if not row:
                    continue
                stats['peak_payload_words'] = max(stats['peak_payload_words'],
                                                 (len(pivots)+1)*width)
                charge(len(row))
                bits, proof = 0, e
                for m in row:
                    bits ^= 1 << positions[m | multiplier]
                if multiplier:
                    proof = emit(['mul', e, multiplier])
                first = 0
                while True:
                    if not bits:
                        for _ in range(width-first):
                            charge()
                        break
                    c = (bits & -bits).bit_length()-1
                    for _ in range(c//64-first+1):
                        charge()
                    first = c//64
                    if c not in pivots:
                        pivots[c] = (bits, proof)
                        stats['pivots'] += 1
                        tables.note(c)
                        break
                    reduced = tables.reduce(bits, proof, c, pivots)
                    bits, proof = reduced if reduced is not None else xor(bits, proof, c, False)
        ordered = sorted(pivots)

        def select():
            leads = []
            for c in reversed(ordered):
                for lm in leads:
                    charge()
                    if lm & columns[c] == lm:
                        break
                else:
                    leads.append(columns[c])
                    yield c

        if minimal:
            charge(len(columns))
            kept = list(select())
            for c in kept:
                bits, proof = pivots[c]
                for later in ordered:
                    if later <= c:
                        continue
                    charge()
                    if (bits >> later) & 1:
                        bits, proof = xor(bits, proof, later, True)
                pivots[c] = bits, proof
        else:
            for i in reversed(range(len(ordered))):
                c = ordered[i]
                for earlier in ordered[:i]:
                    charge()
                    bits, proof = pivots[earlier]
                    if (bits >> c) & 1:
                        pivots[earlier] = xor(bits, proof, c, True)
            kept = select()
        for c in kept:
            bits, proof = pivots[c]
            # Charge each visited word even if it is zero.
            terms = []
            for word in range(c//64, width):
                charge()
                chunk = (bits >> (64*word)) & ((1 << 64)-1)
                while chunk:
                    charge()
                    bit = chunk & -chunk
                    terms.append(columns[64*word+bit.bit_length()-1])
                    chunk ^= bit
            basis.append(sorted(terms))
            outputs.append(proof)
            stats['kept_rows'] += 1
        if retain_raw:
            proof = dict(version=1, nvars=n, order='grevlex-x0-first', nodes=graph, outputs=outputs)
            return dict(stats=stats, basis=basis, proof=proof, reason=None,
                        **(dict(block=block_stats) if block else {}))
        needed = set(outputs)
        for i in reversed(range(len(graph))):
            charge()
            if i in needed:
                node = graph[i]
                if node[0] != 'input':
                    needed.add(node[1])
                if node[0] == 'xor':
                    needed.add(node[2])
        remap, compact = {}, []
        for i, node in enumerate(graph):
            charge()
            if i not in needed:
                continue
            remap[i] = len(compact)
            compact.append([node[0], remap[node[1]] if node[0] != 'input' else node[1]]+
                ([remap[node[2]]] if node[0] == 'xor' else [node[2]] if node[0] == 'mul' else []))
        stats['output_nodes'] = len(compact)
        proof = dict(version=1, nvars=n, order='grevlex-x0-first', nodes=compact,
                     outputs=[remap[i] for i in outputs])
        return dict(stats=stats, basis=basis, proof=proof, reason=None, **(dict(block=block_stats) if block else {}))
    except Limit as exc:
        stats['status'] = 2
        return dict(stats=stats, basis=None, proof=None, reason=str(exc), **(dict(block=block_stats) if block else {}))
