"""Packed squarefree Boolean F5B prototype.

Monomials are integer variable masks. A polynomial is one Python integer whose
bits are monomials in ascending grevlex rank. Addition is integer XOR and
multiplication uses squarefree union with GF(2) cancellation. The labeled-pair
flow follows SymPy's F5B implementation, adapted to the Boolean quotient where
x_i^2 = x_i.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

from macaulay_cache import MacaulayCache, monomial_layout, ring_identity

try:
    from boolean_native import interreduce as native_interreduce
except ImportError:
    native_interreduce = None


Polynomial = int
Signature = tuple[int, int]  # monomial mask, generator index


@dataclass(frozen=True)
class Labeled:
    signature: Signature
    polynomial: Polynomial
    number: int


class BooleanF5B:
    def __init__(self, nvars: int, timeout: float | None = None,
                 max_pairs: int = 1_000_000,
                 max_signature_insertions: int | None = None,
                 matrix_cache: MacaulayCache | None = None):
        self.nvars = nvars
        self.matrix_cache = matrix_cache
        self.deadline = None if timeout is None else time.monotonic() + timeout
        self.max_pairs = max_pairs
        self.max_signature_insertions = max_signature_insertions
        self.stats = {
            "critical_pairs_processed": 0,
            "critical_pairs_discarded": 0,
            "critical_pairs_removed": 0,
            "product_pairs_skipped": 0,
            "reductions": 0,
            "reductions_to_zero": 0,
            "basis_insertions": 0,
            "completion_pairs": 0,
            "completion_insertions": 0,
            "interreduce_passes": 0,
            "interreduce_removed": 0,
            "multiply_cache_hits": 0,
            "multiply_cache_misses": 0,
            "signature_truncated": False,
            "reduction_table_builds": 0,
            "reduction_table_rows": 0,
            "reduction_table_hits": 0,
            "reduction_table_collapses": 0,
            "rewrite_index_lookups": 0,
            "rewrite_index_hits": 0,
            "syzygy_index_lookups": 0,
            "syzygy_index_hits": 0,
            "syzygies_indexed": 0,
            "batch_reductions": 0,
            "batch_input_rows": 0,
            "batch_independent_rows": 0,
            "signature_batches": 0,
            "signature_batch_rows": 0,
            "signature_batch_eliminations": 0,
            "signature_batch_size": 16,
            "completion_batch_size": 64,
            "native_interreduce_calls": 0,
            "native_interreduce_used": False,
        }
        self._monomial_mask = (1 << nvars) - 1
        self._mask_by_rank = monomial_layout(
            nvars, nvars, cache=matrix_cache, max_columns=1 << nvars)
        ranks = [0] * (1 << nvars)
        for rank, monomial in enumerate(self._mask_by_rank):
            ranks[monomial] = rank
        self._rank_by_mask = tuple(ranks)
        self.constant_one = 1 << self._rank_by_mask[0]
        self._multiply_cache: dict[tuple[int, int], int] = {}
        self._rewrite_tables: dict[int, list[int]] = {}
        self._syzygy_tables: dict[int, bytearray] = {}

    def _check_budget(self) -> None:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise TimeoutError("Boolean F5B deadline")
        if self.stats["critical_pairs_processed"] >= self.max_pairs:
            raise TimeoutError("Boolean F5B critical-pair budget")

    def order_key(self, monomial: int) -> int:
        return self._rank_by_mask[monomial]

    @staticmethod
    def divides(left: int, right: int) -> bool:
        return left & ~right == 0

    def leading(self, polynomial: Polynomial) -> int:
        return self._mask_by_rank[polynomial.bit_length() - 1]

    def from_terms(self, terms) -> Polynomial:
        polynomial = 0
        for monomial in terms:
            polynomial ^= 1 << self._rank_by_mask[monomial]
        return polynomial

    def terms(self, polynomial: Polynomial):
        value = polynomial
        while value:
            bit = value & -value
            yield self._mask_by_rank[bit.bit_length() - 1]
            value ^= bit

    @staticmethod
    def add(left: Polynomial, right: Polynomial) -> Polynomial:
        return left ^ right

    def multiply_monomial(self, polynomial: Polynomial,
                          monomial: int) -> Polynomial:
        key = (polynomial, monomial)
        cached = self._multiply_cache.get(key)
        if cached is not None:
            self.stats["multiply_cache_hits"] += 1
            return cached
        self.stats["multiply_cache_misses"] += 1
        result = 0
        value = polynomial
        while value:
            bit = value & -value
            term = self._mask_by_rank[bit.bit_length() - 1]
            result ^= 1 << self._rank_by_mask[term | monomial]
            value ^= bit
        if len(self._multiply_cache) >= 32768:
            self._multiply_cache.clear()
        self._multiply_cache[key] = result
        return result

    def _supersets(self, monomial: int):
        free = self._monomial_mask & ~monomial
        subset = free
        while True:
            yield monomial | subset
            if subset == 0:
                break
            subset = (subset - 1) & free

    def add_reducer(self, rows: list[int], reducer: Polynomial) -> None:
        reducer_lead = self.leading(reducer)
        for target in self._supersets(reducer_lead):
            product = self.multiply_monomial(reducer, target & ~reducer_lead)
            if not product or self.leading(product) != target:
                self.stats["reduction_table_collapses"] += 1
                continue
            current = rows[target]
            if not current or product.bit_count() < current.bit_count():
                rows[target] = product

    def reduction_table(self, reducers: list[Polynomial]) -> list[int]:
        def build():
            rows = [0] * (1 << self.nvars)
            for reducer in reducers:
                if reducer:
                    self.add_reducer(rows, reducer)
            self.stats["reduction_table_builds"] += 1
            self.stats["reduction_table_rows"] += sum(bool(row) for row in rows)
            return rows

        if self.matrix_cache is None:
            return build()
        self._check_budget()
        # This is the engine's selected Macaulay reducer-multiple table, not
        # the complete degree-D matrix. Order matters for equal-weight ties.
        # Bump the kind version when add_reducer's row selection changes.
        spec = {"kind": "boolean-reducer-multiples-v1",
                "ring": ring_identity(self.nvars),
                "reducers": [hex(reducer) for reducer in reducers]}
        rows = self.matrix_cache.get_or_build(
            spec, 1 << self.nvars, 1 << self.nvars, build)
        self._check_budget()
        # Callers append reducers in-place; never expose the cached snapshot.
        return list(rows)

    def index_signature(self, labeled: Labeled) -> None:
        monomial, index = labeled.signature
        table = self._rewrite_tables.setdefault(index, [0] * (1 << self.nvars))
        for multiple in self._supersets(monomial):
            if labeled.number > table[multiple]:
                table[multiple] = labeled.number

    def index_syzygy(self, signature: Signature) -> None:
        monomial, index = signature
        table = self._syzygy_tables.setdefault(
            index, bytearray(1 << self.nvars))
        changed = False
        for multiple in self._supersets(monomial):
            if not table[multiple]:
                table[multiple] = 1
                changed = True
        if changed:
            self.stats["syzygies_indexed"] += 1

    def normal_form(self, polynomial: Polynomial,
                    reducers: list[Polynomial],
                    reduction_rows: list[int] | None = None) -> Polynomial:
        value = polynomial
        remainder = 0
        indexed = None if reduction_rows is not None else [
            (self.leading(candidate), candidate)
            for candidate in reducers if candidate]
        while value:
            self._check_budget()
            lead = self.leading(value)
            if reduction_rows is not None:
                row = reduction_rows[lead]
                if row:
                    value ^= row
                    self.stats["reductions"] += 1
                    self.stats["reduction_table_hits"] += 1
                    continue
                lead_bit = 1 << self._rank_by_mask[lead]
                remainder ^= lead_bit
                value ^= lead_bit
                continue
            reduction = next(((reducer_lead, candidate)
                              for reducer_lead, candidate in indexed
                              if self.divides(reducer_lead, lead)), None)
            if reduction is None:
                lead_bit = 1 << self._rank_by_mask[lead]
                remainder ^= lead_bit
                value ^= lead_bit
                continue
            reducer_lead, reducer = reduction
            multiplier = lead & ~reducer_lead
            value = self.add(value, self.multiply_monomial(reducer, multiplier))
            self.stats["reductions"] += 1
        return remainder

    def signature_key(self, signature: Signature) -> tuple:
        monomial, index = signature
        return (-index, self.order_key(monomial))

    def labeled_key(self, labeled: Labeled) -> tuple:
        return (self.signature_key(labeled.signature), -labeled.number)

    @staticmethod
    def multiply_signature(signature: Signature, monomial: int) -> Signature:
        return (signature[0] | monomial, signature[1])

    def multiply_labeled(self, labeled: Labeled, monomial: int) -> Labeled:
        return Labeled(self.multiply_signature(labeled.signature, monomial),
                       self.multiply_monomial(labeled.polynomial, monomial),
                       labeled.number)

    def subtract_labeled(self, left: Labeled, right: Labeled) -> Labeled:
        maximum = right if self.labeled_key(left) < self.labeled_key(right) else left
        return Labeled(maximum.signature,
                       self.add(left.polynomial, right.polynomial), maximum.number)

    def critical_pair(self, left: Labeled, right: Labeled) -> tuple:
        left_lead = self.leading(left.polynomial)
        right_lead = self.leading(right.polynomial)
        common = left_lead | right_lead
        left_multiplier = common & ~left_lead
        right_multiplier = common & ~right_lead
        left_product = self.multiply_labeled(
            Labeled(left.signature,
                    1 << self._rank_by_mask[left_lead], left.number),
            left_multiplier)
        right_product = self.multiply_labeled(
            Labeled(right.signature,
                    1 << self._rank_by_mask[right_lead], right.number),
            right_multiplier)
        if self.labeled_key(left_product) < self.labeled_key(right_product):
            return (right_product.signature, right_multiplier, right,
                    left_product.signature, left_multiplier, left)
        return (left_product.signature, left_multiplier, left,
                right_product.signature, right_multiplier, right)

    def critical_pair_key(self, pair: tuple) -> tuple:
        return (self.labeled_key(Labeled(pair[0], 0, pair[2].number)),
                self.labeled_key(Labeled(pair[3], 0, pair[5].number)))

    def redundant(self, signature: Signature, number: int,
                  basis: list[Labeled]) -> bool:
        monomial, index = signature
        for labeled in basis:
            other_monomial, other_index = labeled.signature
            # The polynomial-ring comparable criterion is not automatically
            # sound after quotienting by x_i^2+x_i; retain only signature
            # rewrites until a Boolean-specific syzygy proof is implemented.
            if index == other_index and number < labeled.number and self.divides(
                    other_monomial, monomial):
                return True
        return False

    def redundant_indexed(self, signature: Signature, number: int) -> bool:
        monomial, index = signature
        self.stats["syzygy_index_lookups"] += 1
        syzygies = self._syzygy_tables.get(index)
        if syzygies is not None and syzygies[monomial]:
            self.stats["syzygy_index_hits"] += 1
            return True
        self.stats["rewrite_index_lookups"] += 1
        table = self._rewrite_tables.get(index)
        redundant = table is not None and table[monomial] > number
        if redundant:
            self.stats["rewrite_index_hits"] += 1
        return redundant

    def signature_reduce(self, labeled: Labeled,
                         basis: list[Labeled]) -> Labeled:
        value = labeled
        indexed = [(reducer, self.leading(reducer.polynomial))
                   for reducer in basis if reducer.polynomial]
        while value.polynomial:
            self._check_budget()
            previous = value
            lead = self.leading(value.polynomial)
            for reducer, reducer_lead in indexed:
                if not self.divides(reducer_lead, lead):
                    continue
                multiplier = lead & ~reducer_lead
                candidate_signature = self.multiply_signature(
                    reducer.signature, multiplier)
                if self.signature_key(candidate_signature) < self.signature_key(
                        value.signature):
                    value = self.subtract_labeled(
                        value, self.multiply_labeled(reducer, multiplier))
                    self.stats["reductions"] += 1
                    break
            if value == previous:
                break
        return value

    def reduce_basis(self, basis: list[Polynomial]) -> list[Polynomial]:
        minimal: list[Polynomial] = []
        pending = sorted(basis, key=lambda p: self.order_key(self.leading(p)))
        while pending:
            polynomial = pending.pop()
            if not any(self.divides(self.leading(other), self.leading(polynomial))
                       for other in pending + minimal):
                minimal.append(polynomial)
        reduced = []
        for i, polynomial in enumerate(minimal):
            remainder = self.normal_form(polynomial,
                                         minimal[:i] + minimal[i + 1:])
            if remainder:
                reduced.append(remainder)
        return sorted(reduced, key=lambda p: self.order_key(self.leading(p)),
                      reverse=True)

    def is_groebner(self, basis: list[Polynomial]) -> bool:
        rows = self.reduction_table(basis)
        for i, left in enumerate(basis):
            for right in basis[i + 1:]:
                common = self.leading(left) | self.leading(right)
                s_polynomial = self.add(
                    self.multiply_monomial(left, common & ~self.leading(left)),
                    self.multiply_monomial(right, common & ~self.leading(right)))
                if self.normal_form(s_polynomial, basis, rows):
                    return False
        return True

    def row_echelon(self, rows: list[Polynomial]) -> list[Polynomial]:
        pivots: dict[int, Polynomial] = {}
        for original in rows:
            row = original
            while row:
                pivot = row.bit_length() - 1
                reducer = pivots.get(pivot)
                if reducer is None:
                    pivots[pivot] = row
                    break
                row ^= reducer
        return [pivots[pivot] for pivot in sorted(pivots, reverse=True)]

    def complete_basis(self, basis: list[Polynomial]) -> list[Polynomial]:
        completed = list(basis)
        reduction_rows = self.reduction_table(completed)
        pairs = []
        for i in range(len(completed)):
            for j in range(i + 1, len(completed)):
                if self.leading(completed[i]) & self.leading(completed[j]) == 0:
                    self.stats["product_pairs_skipped"] += 1
                else:
                    pairs.append((i, j))
        batch_size = self.stats["completion_batch_size"]
        while pairs:
            self._check_budget()
            batch = [pairs.pop() for _ in range(min(batch_size, len(pairs)))]
            remainders = []
            for i, j in batch:
                self.stats["completion_pairs"] += 1
                left, right = completed[i], completed[j]
                common = self.leading(left) | self.leading(right)
                s_polynomial = self.add(
                    self.multiply_monomial(left, common & ~self.leading(left)),
                    self.multiply_monomial(right, common & ~self.leading(right)))
                remainder = self.normal_form(
                    s_polynomial, completed, reduction_rows)
                if remainder and remainder not in completed:
                    remainders.append(remainder)
            self.stats["batch_reductions"] += 1
            self.stats["batch_input_rows"] += len(remainders)
            independent = self.row_echelon(remainders)
            self.stats["batch_independent_rows"] += len(independent)
            for candidate in independent:
                remainder = self.normal_form(candidate, completed, reduction_rows)
                if not remainder or remainder in completed:
                    continue
                position = len(completed)
                completed.append(remainder)
                self.add_reducer(reduction_rows, remainder)
                for k in range(position):
                    if self.leading(completed[k]) & self.leading(remainder) == 0:
                        self.stats["product_pairs_skipped"] += 1
                    else:
                        pairs.append((k, position))
                self.stats["completion_insertions"] += 1
        return completed

    def interreduce_generators(self, basis: list[Polynomial]) -> list[Polynomial]:
        current = list(dict.fromkeys(basis))
        current.sort(key=lambda polynomial: (
            max((monomial.bit_count() for monomial in self.terms(polynomial)),
                default=0),
            polynomial.bit_count(), self.order_key(self.leading(polynomial))))
        if native_interreduce is not None:
            native = native_interreduce(
                current, self._mask_by_rank, self._rank_by_mask)
            if native is not None:
                current, reductions, passes, removed = native
                self.stats["native_interreduce_calls"] += 1
                self.stats["native_interreduce_used"] = True
                self.stats["reductions"] += reductions
                self.stats["interreduce_passes"] += passes
                self.stats["interreduce_removed"] += removed
                return current
        while True:
            self._check_budget()
            self.stats["interreduce_passes"] += 1
            changed = False
            i = 0
            while i < len(current):
                polynomial = current[i]
                others = current[:i] + current[i + 1:]
                remainder = self.normal_form(polynomial, others)
                if remainder == polynomial:
                    i += 1
                    continue
                changed = True
                if remainder:
                    current[i] = remainder
                    i += 1
                else:
                    del current[i]
                    self.stats["interreduce_removed"] += 1
            if not changed:
                return current

    def basis(self, generators: list[Polynomial]) -> list[Polynomial]:
        started = time.monotonic()
        current = [polynomial for polynomial in generators if polynomial]
        while True:
            reduced = []
            for i, polynomial in enumerate(current):
                remainder = self.normal_form(polynomial, current[:i])
                if remainder:
                    reduced.append(remainder)
            if reduced == current:
                break
            current = reduced
        labeled_basis = [Labeled((0, i + 1), polynomial, i + 1)
                         for i, polynomial in enumerate(current)]
        for labeled in labeled_basis:
            self.index_signature(labeled)
        labeled_basis.sort(key=lambda f: self.order_key(
            self.leading(f.polynomial)), reverse=True)
        pairs = []
        for i in range(len(labeled_basis)):
            for j in range(i + 1, len(labeled_basis)):
                if (self.leading(labeled_basis[i].polynomial) &
                        self.leading(labeled_basis[j].polynomial)) == 0:
                    self.stats["product_pairs_skipped"] += 1
                else:
                    pairs.append(self.critical_pair(
                        labeled_basis[i], labeled_basis[j]))
        pairs.sort(key=self.critical_pair_key, reverse=True)
        main_reduction_rows = self.reduction_table(
            [item.polynomial for item in labeled_basis])
        number = len(labeled_basis)
        signature_batch_size = self.stats["signature_batch_size"]
        stop_signatures = False
        while pairs and not stop_signatures:
            self._check_budget()
            selected = [pairs.pop() for _ in range(
                min(signature_batch_size, len(pairs)))]
            candidates = []
            for pair in selected:
                self.stats["critical_pairs_processed"] += 1
                if self.redundant_indexed(pair[0], pair[2].number) or \
                        self.redundant_indexed(pair[3], pair[5].number):
                    self.stats["critical_pairs_discarded"] += 1
                    continue
                left = self.multiply_labeled(pair[2], pair[1])
                right = self.multiply_labeled(pair[5], pair[4])
                candidate = self.signature_reduce(
                    self.subtract_labeled(left, right), labeled_basis)
                ordinary = self.normal_form(
                    candidate.polynomial,
                    [item.polynomial for item in labeled_basis],
                    main_reduction_rows)
                if ordinary:
                    candidates.append(Labeled(candidate.signature, ordinary,
                                              candidate.number))
                else:
                    self.stats["reductions_to_zero"] += 1
                    self.index_syzygy(candidate.signature)
            candidates.sort(key=lambda candidate:
                            self.signature_key(candidate.signature))
            pivots: dict[int, Labeled] = {}
            independent = []
            for candidate in candidates:
                polynomial = candidate.polynomial
                while polynomial:
                    pivot = polynomial.bit_length() - 1
                    reducer = pivots.get(pivot)
                    if reducer is None:
                        accepted = Labeled(candidate.signature, polynomial,
                                           candidate.number)
                        pivots[pivot] = accepted
                        independent.append(accepted)
                        break
                    polynomial ^= reducer.polynomial
                    self.stats["signature_batch_eliminations"] += 1
            self.stats["signature_batches"] += 1
            self.stats["signature_batch_rows"] += len(candidates)
            for pending in independent:
                ordinary = self.normal_form(
                    pending.polynomial,
                    [item.polynomial for item in labeled_basis],
                    main_reduction_rows)
                if not ordinary:
                    self.stats["reductions_to_zero"] += 1
                    self.index_syzygy(pending.signature)
                    continue
                number += 1
                candidate = Labeled(pending.signature, ordinary, number)
                self.index_signature(candidate)
                self.add_reducer(main_reduction_rows, candidate.polynomial)
                retained = []
                for old in pairs:
                    if self.redundant_indexed(old[0], old[2].number) or \
                            self.redundant_indexed(old[3], old[5].number):
                        self.stats["critical_pairs_removed"] += 1
                    else:
                        retained.append(old)
                pairs = retained
                for existing in labeled_basis:
                    if (self.leading(candidate.polynomial) &
                            self.leading(existing.polynomial)) == 0:
                        self.stats["product_pairs_skipped"] += 1
                        continue
                    new_pair = self.critical_pair(candidate, existing)
                    if self.redundant_indexed(
                            new_pair[0], new_pair[2].number) or \
                            self.redundant_indexed(
                                new_pair[3], new_pair[5].number):
                        self.stats["critical_pairs_discarded"] += 1
                        continue
                    pairs.append(new_pair)
                labeled_basis.append(candidate)
                self.stats["basis_insertions"] += 1
                if (self.max_signature_insertions is not None and
                        self.stats["basis_insertions"] >=
                        self.max_signature_insertions):
                    self.stats["signature_truncated"] = True
                    stop_signatures = True
                    break
            pairs.sort(key=self.critical_pair_key, reverse=True)
            labeled_basis.sort(key=lambda f: self.order_key(
                self.leading(f.polynomial)), reverse=True)
        interreduced = self.interreduce_generators(
            [item.polynomial for item in labeled_basis])
        completed = self.complete_basis(interreduced)
        result = self.reduce_basis(completed)
        self.stats["seconds"] = time.monotonic() - started
        self.stats["basis_size"] = len(result)
        self.stats["groebner_verified"] = self.is_groebner(result)
        if not self.stats["groebner_verified"]:
            raise AssertionError("Boolean signature basis failed S-pair completion")
        self.stats["basis_sha256"] = hashlib.sha256(json.dumps(
            [sorted(self.terms(polynomial)) for polynomial in result],
            sort_keys=True).encode()).hexdigest()
        return result

    def evaluate(self, polynomial: Polynomial, assignment: int) -> int:
        value = 0
        for monomial in self.terms(polynomial):
            value ^= monomial & ~assignment == 0
        return int(value)

    def same_roots(self, left: list[Polynomial], right: list[Polynomial]) -> bool:
        for assignment in range(1 << self.nvars):
            if all(self.evaluate(p, assignment) == 0 for p in left) != all(
                    self.evaluate(p, assignment) == 0 for p in right):
                return False
        return True
