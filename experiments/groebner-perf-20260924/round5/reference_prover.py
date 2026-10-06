"""Small sparse Buchberger proof producer; independent of the verifier.

This is a correctness/proof-format reference, not a fast F4/F5 replacement.
Sorted tuples and parity cancellation are used instead of verifier sets.
"""
from dataclasses import dataclass
import heapq
from itertools import groupby


class ProverBudget(Exception):
    pass


@dataclass(frozen=True)
class Witnessed:
    terms: tuple
    node: int


def prove(nvars, equations, *, max_work=2_000_000, max_nodes=100_000):
    if type(nvars) is not int or not 1 <= nvars <= 4096:
        raise ValueError('variables must be in 1..4096')
    nodes, basis, queue = [], [], []
    work = 0

    def spend(amount=1):
        nonlocal work
        work += amount
        if work > max_work or len(nodes) >= max_nodes:
            raise ProverBudget(f'reference proof-production budget: work={work}, nodes={len(nodes)}')

    def normalize(terms):
        spend(len(terms))
        return tuple(term for term, group in groupby(sorted(terms)) if sum(1 for _ in group) % 2)

    def emit(terms, instruction):
        spend()
        nodes.append(instruction)
        return Witnessed(terms,len(nodes)-1)

    def key(mask):
        return mask.bit_count(), -mask

    def lead(element):
        return max(element.terms,key=key)

    def product(element, mask):
        return emit(normalize([mask | term for term in element.terms]),['mul',element.node,mask])

    def addition(left, right):
        return emit(normalize(left.terms+right.terms),['xor',left.node,right.node])

    def reduce(element, reducers):
        indexed = [(lead(row),row) for row in reducers]
        while element.terms:
            reduction = None
            for term in sorted(element.terms,key=key,reverse=True):
                for lm, row in indexed:
                    spend()
                    if (term | lm) == term:
                        reduction = term ^ lm, row
                        break
                if reduction is not None:
                    break
            if reduction is None:
                break
            mask, row = reduction
            element = addition(element,product(row,mask))
        return element

    def install(element):
        index = len(basis)
        lm = lead(element)
        for j, other in enumerate(basis):
            spend()
            other_lm = lead(other)
            if lm & other_lm:  # product criterion only; verifier checks all pairs
                heapq.heappush(queue,((lm | other_lm).bit_count(),index,j))
        bits = lm
        while bits:
            bit = bits & -bits
            bits ^= bit
            heapq.heappush(queue,(lm.bit_count()+1,index,-bit))
        basis.append(element)

    for i, equation in enumerate(equations):
        if any(type(mask) is not int or not 0 <= mask < 1 << nvars for mask in equation):
            raise ValueError('invalid monomial')
        candidate = reduce(emit(normalize(equation),['input',i]),basis)
        if candidate.terms:
            install(candidate)
    while queue and not any(row.terms == (0,) for row in basis):
        spend()
        checkpoint = len(nodes)
        _, i, j = heapq.heappop(queue)
        left = basis[i]
        if j < 0:
            pair = product(left,-j)
        else:
            right = basis[j]
            common = lead(left) | lead(right)
            pair = addition(product(left,common ^ lead(left)),product(right,common ^ lead(right)))
        candidate = reduce(pair,basis)
        if candidate.terms:
            install(candidate)
        else:
            # A zero pair contributes no output derivation. No basis row can
            # reference these temporary nodes, so they need not be retained.
            del nodes[checkpoint:]
    # Sequential interreduction retains a witness for every replaced row.
    changed = True
    while changed:
        changed = False
        for i, row in enumerate(basis):
            reduced = reduce(row,basis[:i]+basis[i+1:])
            if reduced.terms != row.terms:
                basis[i:i+1] = [reduced] if reduced.terms else []
                changed = True
                break
    basis.sort(key=lambda row:key(lead(row)),reverse=True)
    # Keep only the transitive ancestry of the final outputs. Completion and
    # interreduction often leave derivations that are no longer needed.
    reachable, pending = set(), [row.node for row in basis]
    while pending:
        index = pending.pop()
        if index in reachable:
            continue
        reachable.add(index)
        node = nodes[index]
        if node[0] == 'mul':
            pending.append(node[1])
        elif node[0] == 'xor':
            pending.extend(node[1:])
    remap = {old:new for new,old in enumerate(sorted(reachable))}
    compact = []
    for old in sorted(reachable):
        node = nodes[old]
        if node[0] == 'mul':
            node = ['mul',remap[node[1]],node[2]]
        elif node[0] == 'xor':
            node = ['xor',remap[node[1]],remap[node[2]]]
        compact.append(node)
    return {'basis': [list(row.terms) for row in basis],
            'proof': {'version':1,'nvars':nvars,'order':'grevlex-x0-first',
                      'nodes':compact,'outputs':[remap[row.node] for row in basis]},
            'producer_work':work}
