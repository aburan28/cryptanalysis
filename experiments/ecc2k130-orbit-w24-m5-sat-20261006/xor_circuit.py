"""Self-contained native-XOR SAT circuit for GF(2^131) polynomial arithmetic."""

from collections import Counter
import resource
import sys


class Circuit:
    # Wire 0 is false, -1 is true, and positive integers are XCNF variables.
    def __init__(self, n, low_terms, memory_limit_bytes=None):
        self.n = n
        self.modulus = (1 << n) | sum(1 << i for i in low_terms)
        self.next_var = 1
        self.clauses = []
        self.xors = []
        self.and_cache = {}
        self.xor_cache = {}
        self.red = [self.reduce(1 << k) for k in range(2*n - 1)]
        self.square_red = [self.red[2*i] for i in range(n)]
        self.and_count = 0
        self.memory_limit_bytes = memory_limit_bytes

    def check_memory(self):
        if self.memory_limit_bytes is None:
            return
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            peak *= 1024
        if peak > self.memory_limit_bytes:
            raise MemoryError("circuit builder exceeded frozen RSS limit")

    def reduce(self, value):
        while value.bit_length() > self.n:
            value ^= self.modulus << (value.bit_length() - self.n - 1)
        return value

    def variable(self):
        result = self.next_var
        self.next_var += 1
        return result

    def and_(self, left, right):
        if left == 0 or right == 0:
            return 0
        if left == -1:
            return right
        if right == -1 or left == right:
            return left
        key = tuple(sorted((left, right)))
        if key in self.and_cache:
            return self.and_cache[key]
        output = self.variable()
        self.clauses.extend((f"-{left} -{right} {output} 0",
                             f"{left} -{output} 0",
                             f"{right} -{output} 0"))
        self.and_cache[key] = output
        self.and_count += 1
        if self.and_count % 4096 == 0:
            self.check_memory()
        return output

    def xor(self, items):
        parity = 0
        counts = Counter()
        for wire in items:
            if wire == -1:
                parity ^= 1
            elif wire:
                counts[wire] ^= 1
        terms = tuple(sorted(wire for wire, count in counts.items() if count))
        if not terms:
            return -1 if parity else 0
        if len(terms) == 1 and not parity:
            return terms[0]
        key = (terms, parity)
        if key in self.xor_cache:
            return self.xor_cache[key]
        output = self.variable()
        # CMS XCNF means XOR(literals) = true.
        self.xors.append("x " + str(output if parity else -output) +
                          " " + " ".join(map(str, terms)) + " 0")
        self.xor_cache[key] = output
        if len(self.xors) % 8192 == 0:
            self.check_memory()
        return output

    def constant(self, value):
        return [-1 if (value >> i) & 1 else 0 for i in range(self.n)]

    def add(self, left, right):
        return [self.xor((a, b)) for a, b in zip(left, right)]

    def add_many(self, values):
        result = self.constant(0)
        for value in values:
            result = self.add(result, value)
        return result

    def square(self, value):
        buckets = [[] for _ in range(self.n)]
        for i, wire in enumerate(value):
            if not wire:
                continue
            image = self.square_red[i]
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(wire)
                image ^= low
        return [self.xor(bucket) for bucket in buckets]

    def linear_element(self, variables, values, constant=0):
        buckets = [[-1] if (constant >> i) & 1 else []
                   for i in range(self.n)]
        for wire, value in zip(variables, values):
            while value:
                low = value & -value
                buckets[low.bit_length()-1].append(wire)
                value ^= low
        return [self.xor(bucket) for bucket in buckets]

    def require_zero(self, value):
        for wire in value:
            if wire == -1:
                self.clauses.append("0")
            elif wire:
                self.clauses.append(f"-{wire} 0")

    def require_nonzero(self, value):
        if -1 in value:
            return
        wires = sorted(set(wire for wire in value if wire > 0))
        self.clauses.append(" ".join(map(str, wires)) + " 0")

    def pin(self, wire, truth):
        assert wire > 0
        self.clauses.append(f"{wire if truth else -wire} 0")

    def forbid_above(self, row, bound):
        # Lexicographic constant comparison uses one clause per zero bit.
        for bit in range(len(row)-1, -1, -1):
            if (bound >> bit) & 1:
                continue
            clause = [-row[bit]]
            for higher in range(bit+1, len(row)):
                clause.append(-row[higher] if (bound >> higher) & 1
                              else row[higher])
            self.clauses.append(" ".join(map(str, clause)) + " 0")

    def _schoolbook(self, left, right):
        buckets = [[] for _ in range(len(left)+len(right)-1)]
        for i, a in enumerate(left):
            if not a:
                continue
            for j, b in enumerate(right):
                if b:
                    buckets[i+j].append(self.and_(a, b))
        return [self.xor(bucket) for bucket in buckets]

    def _polynomial_mul(self, left, right):
        size = len(left)
        assert len(right) == size and size & (size-1) == 0
        if not any(left) or not any(right):
            return [0]*(2*size-1)
        if size <= 8 or sum(bool(x) for x in left)*sum(bool(x) for x in right) <= 64:
            return self._schoolbook(left, right)
        half = size//2
        low = self._polynomial_mul(left[:half], right[:half])
        high = self._polynomial_mul(left[half:], right[half:])
        folded_left = [self.xor((left[i], left[i+half])) for i in range(half)]
        folded_right = [self.xor((right[i], right[i+half])) for i in range(half)]
        middle = self._polynomial_mul(folded_left, folded_right)
        buckets = [[] for _ in range(2*size-1)]
        for i, wire in enumerate(low):
            buckets[i].append(wire)
            buckets[i+half].append(wire)
        for i, wire in enumerate(high):
            buckets[i+half].append(wire)
            buckets[i+2*half].append(wire)
        for i, wire in enumerate(middle):
            buckets[i+half].append(wire)
        return [self.xor(bucket) for bucket in buckets]

    def mul(self, left, right):
        size = 1 << (self.n-1).bit_length()
        polynomial = self._polynomial_mul(
            list(left)+[0]*(size-self.n), list(right)+[0]*(size-self.n))
        buckets = [[] for _ in range(self.n)]
        for exponent, wire in enumerate(polynomial):
            if not wire or exponent >= 2*self.n-1:
                continue
            image = self.red[exponent]
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(wire)
                image ^= low
        return [self.xor(bucket) for bucket in buckets]

    def write(self, path):
        with path.open("x", encoding="ascii") as output:
            output.write(f"p cnf {self.next_var-1} "
                         f"{len(self.clauses)+len(self.xors)}\n")
            for line in self.clauses:
                output.write(line + "\n")
            for line in self.xors:
                output.write(line + "\n")
        self.check_memory()
