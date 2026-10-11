"""Exact binary-field expressions with a variable, low-rank F2 basis."""


class Algebra:
    def __init__(self, circuit, field, dense_and_threshold=942):
        self.circuit = circuit
        self.field = field
        self.dense_and_threshold = dense_and_threshold
        self.sparse_mul_calls = 0
        self.generic_mul_calls = 0
        self.sparse_pair_products = 0
        self.linear_squares = 0
        self.one = self.expression(((-1, 1),))
        self.zero = self.expression(())

    def expression(self, terms):
        # Equal field-basis images can be folded with one XOR. Keep distinct
        # images as separate terms while sparse. Dense conversion uses the
        # field-coordinate linear map once, avoiding one XOR per pivot update.
        groups = {}
        for wire, value in terms:
            if wire == 0 or value == 0:
                continue
            groups.setdefault(value, []).append(wire)
        folded = [(self.circuit.xor(wires), value)
                  for value, wires in sorted(groups.items())]
        folded = [(wire, value) for wire, value in folded if wire != 0]
        if len(folded) > self.circuit.n:
            wires = [wire for wire, _ in folded]
            values = [value for _, value in folded]
            bits = self.circuit.linear_element(wires, values)
            folded = [(wire, 1 << i) for i, wire in enumerate(bits) if wire != 0]
        return Expression(self, tuple(folded))

    def from_bits(self, bits):
        return self.expression((wire, 1 << i) for i, wire in enumerate(bits))

    def add(self, *values):
        return self.expression(term for value in values for term in value.terms)

    def square(self, value):
        self.linear_squares += 1
        return self.expression((wire, self.field.square(basis))
                               for wire, basis in value.terms)

    def mul(self, left, right):
        if not left.terms or not right.terms:
            return self.zero
        if left.is_one():
            return right
        if right.is_one():
            return left
        pair_count = len(left.terms) * len(right.terms)
        if pair_count <= self.dense_and_threshold:
            self.sparse_mul_calls += 1
            self.sparse_pair_products += pair_count
            return self.expression(
                (self.circuit.and_(a_wire, b_wire), self.field.mul(a_value, b_value))
                for a_wire, a_value in left.terms
                for b_wire, b_value in right.terms)
        self.generic_mul_calls += 1
        return self.from_bits(self.circuit.mul(left.bits(), right.bits()))


class Expression:
    def __init__(self, algebra, terms):
        self.algebra = algebra
        self.terms = terms
        self._bits = None

    def is_one(self):
        return self.terms == ((-1, 1),)

    def bits(self):
        if self._bits is None:
            wires = [wire for wire, _ in self.terms]
            values = [value for _, value in self.terms]
            self._bits = self.algebra.circuit.linear_element(wires, values)
        return self._bits
