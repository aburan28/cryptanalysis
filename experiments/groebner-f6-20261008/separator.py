"""Exact Boolean polynomial satisfiability by bounded-width elimination.

The scope of each equation is the union of its monomial variables. Each
factor represents exactly the satisfying assignments to that equation.
Eliminating x joins the factors containing x and existentially projects x;
a witness bit for each projected assignment reconstructs a full solution.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Factor:
    scope: tuple[int, ...]
    allowed: set[int]


class WidthCap(Exception):
    def __init__(self, bag, variables):
        super().__init__(f'bag of {bag} variables exceeds cap')
        self.bag = bag
        self.variables = variables


def canonical(terms):
    present = set()
    for mask in terms:
        if mask in present:
            present.remove(mask)
        else:
            present.add(mask)
    return tuple(sorted(present))


def scope_of(terms):
    support = 0
    for mask in terms:
        support |= mask
    return tuple(i for i in range(support.bit_length()) if support >> i & 1)


def expand(local, scope):
    return sum(((local >> j) & 1) << variable for j, variable in enumerate(scope))


def restrict(local, from_scope, to_scope):
    positions = {v: i for i, v in enumerate(from_scope)}
    return sum(((local >> positions[v]) & 1) << j for j, v in enumerate(to_scope))


def satisfies(terms, assignment):
    return sum((assignment & mask) == mask for mask in terms) % 2 == 0


def equation_factor(n, terms, max_bag):
    terms = canonical(terms)
    if any(mask < 0 or mask >= 1 << n for mask in terms):
        raise ValueError('monomial outside declared Boolean ring')
    scope = scope_of(terms)
    if len(scope) > max_bag:
        raise WidthCap(len(scope), scope)
    allowed = {local for local in range(1 << len(scope))
               if satisfies(terms, expand(local, scope))}
    return Factor(scope, allowed)


def choose(factors, remaining):
    def score(variable):
        bag = {variable}
        for factor in factors:
            if variable in factor.scope:
                bag.update(factor.scope)
        return len(bag), variable
    return min(remaining, key=score)


def solve(n, equations, *, max_bag=12, max_states=1_000_000):
    if not 0 <= n <= 64 or not 0 <= max_bag <= 64:
        raise ValueError('invalid Boolean ring or width cap')
    factors = [equation_factor(n, eq, max_bag) for eq in equations]
    remaining = set(range(n))
    history = []
    work = 0
    width = max((len(f.scope) for f in factors), default=0)
    while remaining:
        x = choose(factors, remaining)
        bucket = [factor for factor in factors if x in factor.scope]
        factors = [factor for factor in factors if x not in factor.scope]
        bag = tuple(sorted({x}.union(*(factor.scope for factor in bucket))))
        width = max(width, len(bag))
        if len(bag) > max_bag:
            raise WidthCap(len(bag), bag)
        states = 1 << len(bag)
        if work + states > max_states:
            return dict(status='state-cap', assignment=None, width=width,
                        enumerated_states=work, eliminated=n-len(remaining))
        keep = tuple(v for v in bag if v != x)
        projections = [(factor, tuple(bag.index(v) for v in factor.scope))
                       for factor in bucket]
        witness = {}
        for local in range(states):
            work += 1
            if all(sum(((local >> pos) & 1) << i for i, pos in enumerate(indices))
                       in factor.allowed for factor, indices in projections):
                projected = restrict(local, bag, keep)
                witness.setdefault(projected, (local >> bag.index(x)) & 1)
        factors.append(Factor(keep, set(witness)))
        history.append((x, keep, witness))
        remaining.remove(x)
        if not witness:
            return dict(status='unsatisfiable', assignment=None, width=width,
                        enumerated_states=work, eliminated=n-len(remaining))
    if any(0 not in factor.allowed for factor in factors):
        return dict(status='unsatisfiable', assignment=None, width=width,
                    enumerated_states=work, eliminated=n)
    assignment = 0
    for x, keep, witness in reversed(history):
        key = restrict(assignment, tuple(range(n)), keep)
        assignment |= witness[key] << x
    assert all(satisfies(canonical(eq), assignment) for eq in equations)
    return dict(status='satisfiable', assignment=assignment, width=width,
                enumerated_states=work, eliminated=n)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fixture', type=Path)
    parser.add_argument('--max-bag', type=int, default=12)
    parser.add_argument('--max-states', type=int, default=1_000_000)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    case = fixture.get('fixture', fixture)
    n, equations = case['nvars'], case['equations']
    try:
        result = solve(n, equations, max_bag=args.max_bag, max_states=args.max_states)
    except WidthCap as error:
        result = dict(status='width-cap', assignment=None, width=error.bag,
                      bag_variables=error.variables)
    result.update(nvars=n, equations=len(equations), max_bag=args.max_bag,
                  max_states=args.max_states)
    encoded = json.dumps(result, indent=2)+'\n'
    if args.output:
        assert not args.output.exists()
        args.output.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
