"""Small exact Boolean polynomial and sparse Macaulay primitives.

This is a stage probe, not a Groebner basis implementation.  Monomials are
squarefree bit masks and polynomials are sets of masks over GF(2).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


def add(*polynomials: set[int]) -> set[int]:
    answer: set[int] = set()
    for polynomial in polynomials:
        answer.symmetric_difference_update(polynomial)
    return answer


def multiply(left: set[int], right: set[int]) -> set[int]:
    answer: set[int] = set()
    for a in left:
        for b in right:
            term = a | b
            if term in answer:
                answer.remove(term)
            else:
                answer.add(term)
    return answer


def evaluate(polynomial: set[int], assignment: int) -> int:
    return sum((term & assignment) == term for term in polynomial) & 1


class ANFField:
    def __init__(self, degree: int, modulus: int):
        if modulus.bit_length() != degree + 1 or not modulus & 1:
            raise ValueError("modulus must have degree n and nonzero constant")
        self.n = degree
        self.modulus = modulus
        self.reductions = tuple(self.reduce(1 << i) for i in range(2 * degree - 1))

    def reduce(self, value: int) -> int:
        while value.bit_length() > self.n:
            value ^= self.modulus << (value.bit_length() - self.n - 1)
        return value

    def constant(self, value: int) -> list[set[int]]:
        return [{0} if value >> i & 1 else set() for i in range(self.n)]

    def linear(self, variables: list[int], coefficients: list[int], constant=0):
        if len(variables) != len(coefficients):
            raise ValueError("one field coefficient per Boolean variable")
        result = self.constant(constant)
        for variable, value in zip(variables, coefficients):
            for bit in range(self.n):
                if value >> bit & 1:
                    result[bit].symmetric_difference_update((1 << variable,))
        return result

    def add(self, *elements):
        return [add(*(element[i] for element in elements)) for i in range(self.n)]

    def square(self, element):
        result = [set() for _ in range(self.n)]
        for i, polynomial in enumerate(element):
            for bit in range(self.n):
                if self.reductions[2 * i] >> bit & 1:
                    result[bit].symmetric_difference_update(polynomial)
        return result

    def mul(self, left, right):
        result = [set() for _ in range(self.n)]
        for i, a in enumerate(left):
            if not a:
                continue
            for j, b in enumerate(right):
                if not b:
                    continue
                product = multiply(a, b)
                for bit in range(self.n):
                    if self.reductions[i + j] >> bit & 1:
                        result[bit].symmetric_difference_update(product)
        return result

    def product(self, *elements):
        answer = self.constant(1)
        for element in elements:
            answer = self.mul(answer, element)
        return answer

    def s3_coefficients(self, left, right):
        ab = self.mul(left, right)
        return self.square(self.add(left, right)), ab, self.add(self.square(ab), self.constant(1))

    def s3(self, left, right, target):
        a, b, c = self.s3_coefficients(left, right)
        return self.add(self.mul(a, self.square(target)), self.mul(b, target), c)

    def s4(self, x1, x2, x3, target):
        """Resultant in z of S3(x1,x2,z) and S3(x3,target,z)."""
        a, b, c = self.s3_coefficients(x1, x2)
        d, e, f = self.s3_coefficients(x3, target)
        return self.add(self.mul(self.square(a), self.square(f)),
                        self.product(a, b, e, f),
                        self.product(a, c, self.square(e)),
                        self.product(self.square(b), d, f),
                        self.product(b, c, d, e),
                        self.mul(self.square(c), self.square(d)))


def monomials(nvars: int, degree: int):
    if nvars < 0 or degree < 0:
        raise ValueError("nonnegative dimensions required")
    return tuple(sum(1 << i for i in indices)
                 for d in range(min(nvars, degree) + 1)
                 for indices in combinations(range(nvars), d))


@dataclass(frozen=True)
class SparseMacaulay:
    columns: tuple[int, ...]
    sources: tuple[tuple[int, int], ...]
    rows: tuple[frozenset[int], ...]

    @property
    def nnz(self):
        return sum(len(row) for row in self.rows)

    def matvec(self, vector: int) -> int:
        answer = 0
        for i, row in enumerate(self.rows):
            if sum(vector >> j & 1 for j in row) & 1:
                answer |= 1 << i
        return answer

    def transposed_matvec(self, vector: int) -> int:
        answer = 0
        for i, row in enumerate(self.rows):
            if vector >> i & 1:
                for j in row:
                    answer ^= 1 << j
        return answer

    def packed_rows(self):
        return tuple(sum(1 << j for j in row) for row in self.rows)


def sparse_macaulay(equations, nvars: int, degree: int, *, fixed_degrees=None,
                    max_columns=1_000_000, max_rows=2_000_000):
    """Build all squarefree multiples up to D, with explicit memory gates."""
    columns = monomials(nvars, degree)
    if len(columns) > max_columns:
        raise ValueError("column limit exceeded")
    positions = {term: i for i, term in enumerate(columns)}
    sources = []
    rows = []
    if fixed_degrees is not None and len(fixed_degrees) != len(equations):
        raise ValueError("fixed degree schedule does not match equations")
    for i, equation in enumerate(equations):
        observed = max((term.bit_count() for term in equation), default=-1)
        maximum = observed if fixed_degrees is None else fixed_degrees[i]
        if maximum < 0:
            if equation:
                raise ValueError("nonzero equation has no degree slot")
            continue
        if observed > maximum:
            raise ValueError("equation exceeds its fixed degree slot")
        if maximum > degree:
            raise ValueError("equation degree exceeds Macaulay degree")
        for multiplier in monomials(nvars, degree - maximum):
            row = set()
            for term in equation:
                column = positions[term | multiplier]
                if column in row:
                    row.remove(column)
                else:
                    row.add(column)
            sources.append((i, multiplier))
            rows.append(frozenset(row))
            if len(rows) > max_rows:
                raise ValueError("row limit exceeded")
    return SparseMacaulay(columns, tuple(sources), tuple(rows))


def echelon(rows: tuple[int, ...]):
    """Forward GF(2) elimination; return rows and exact row-operation trace."""
    work = list(rows)
    steps = []
    pivot = 0
    for column in range(max((row.bit_length() for row in work), default=0) - 1, -1, -1):
        source = next((i for i in range(pivot, len(work)) if work[i] >> column & 1), None)
        if source is None:
            continue
        if source != pivot:
            work[source], work[pivot] = work[pivot], work[source]
            steps.append(("swap", source, pivot))
        for i in range(pivot + 1, len(work)):
            if work[i] >> column & 1:
                work[i] ^= work[pivot]
                steps.append(("xor", pivot, i))
        steps.append(("pivot", pivot, column))
        pivot += 1
        if pivot == len(work):
            break
    return tuple(work), tuple(steps)


def replay_trace(rows: tuple[int, ...], trace, *, verify=True):
    """Replay a captured elimination schedule; reject changed pivots/support."""
    work = list(rows)
    for operation, source, target in trace:
        if operation == "swap":
            work[source], work[target] = work[target], work[source]
        elif operation == "xor":
            work[target] ^= work[source]
        else:
            assert operation == "pivot"
            if not (work[source] >> target & 1):
                return None
            if any(work[i] >> target & 1 for i in range(source + 1, len(work))):
                return None
    if verify:
        fresh, _ = echelon(rows)
        if tuple(work) != fresh:
            return None
    return tuple(work)
