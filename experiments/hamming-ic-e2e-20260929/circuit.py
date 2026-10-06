"""GF(2^n) Boolean XCNF circuit for the S3 point-decomposition query."""

from collections import Counter

class Circuit:
    def __init__(self, n, low_terms):
        self.n = n
        self.modulus = (1 << n) | sum(1 << i for i in low_terms)
        self.next_var = 1
        self.clauses = []
        self.xors = []
        self.and_cache = {}
        self.xor_cache = {}
        self.red = [self.reduce(1 << k) for k in range(2 * n - 1)]
        self.square_red = [self.red[2 * i] for i in range(n)]
        self.and_count = 0

    def reduce(self, x):
        while x.bit_length() > self.n:
            x ^= self.modulus << (x.bit_length() - self.n - 1)
        return x

    def variable(self):
        result = self.next_var
        self.next_var += 1
        return result

    def and_(self, a, b):
        # 0 and -1 represent constants false and true. Other ints are vars.
        if a == 0 or b == 0:
            return 0
        if a == -1:
            return b
        if b == -1:
            return a
        if a == b:
            return a
        key = tuple(sorted((a, b)))
        if key in self.and_cache:
            return self.and_cache[key]
        out = self.variable()
        self.clauses.extend((f"-{a} -{b} {out} 0", f"{a} -{out} 0", f"{b} -{out} 0"))
        self.and_cache[key] = out
        self.and_count += 1
        return out

    def xor(self, items):
        parity = 0
        counts = Counter()
        for v in items:
            if v == -1:
                parity ^= 1
            elif v != 0:
                counts[v] ^= 1
        terms = tuple(sorted(v for v, count in counts.items() if count))
        if not terms:
            return -1 if parity else 0
        if len(terms) == 1 and parity == 0:
            return terms[0]
        key = (terms, parity)
        if key in self.xor_cache:
            return self.xor_cache[key]
        out = self.variable()
        # CryptoMiniSat's 'x' line requires the XOR of its literals = true.
        # Negating out converts parity 0 to the required odd parity.
        first = str(out if parity else -out)
        self.xors.append("x " + first + " " + " ".join(map(str, terms)) + " 0")
        self.xor_cache[key] = out
        return out

    def constant(self, value):
        return [-1 if (value >> i) & 1 else 0 for i in range(self.n)]

    def add(self, a, b):
        return [self.xor((x, y)) for x, y in zip(a, b)]

    def square(self, a):
        buckets = [[] for _ in range(self.n)]
        for i, wire in enumerate(a):
            if wire == 0:
                continue
            reduced = self.square_red[i]
            while reduced:
                low = reduced & -reduced
                buckets[low.bit_length() - 1].append(wire)
                reduced ^= low
        return [self.xor(bucket) for bucket in buckets]

    def sqrt(self, a, field):
        # Frobenius inverse is an F2-linear map in this field representation.
        basis_images = []
        for i in range(self.n):
            value = 1 << i
            for _ in range(self.n - 1):
                value = field.mul(value, value)
            basis_images.append(value)
        buckets = [[] for _ in range(self.n)]
        for wire, image in zip(a, basis_images):
            while image:
                low = image & -image
                buckets[low.bit_length() - 1].append(wire)
                image ^= low
        return [self.xor(bucket) for bucket in buckets]

    def mul(self, a, b):
        buckets = [[] for _ in range(self.n)]
        for i, x in enumerate(a):
            if x == 0:
                continue
            for j, y in enumerate(b):
                if y == 0:
                    continue
                product = self.and_(x, y)
                reduced = self.red[i + j]
                while reduced:
                    low = reduced & -reduced
                    buckets[low.bit_length() - 1].append(product)
                    reduced ^= low
        return [self.xor(bucket) for bucket in buckets]

    def linear_element(self, variables, values, constant=0):
        buckets = [[-1] if (constant >> i) & 1 else [] for i in range(self.n)]
        for var, value in zip(variables, values):
            bits = value
            while bits:
                low = bits & -bits
                buckets[low.bit_length() - 1].append(var)
                bits ^= low
        return [self.xor(bucket) for bucket in buckets]

    def require_zero(self, element):
        for wire in element:
            if wire == -1:
                self.clauses.append("0")
            elif wire != 0:
                self.clauses.append(f"-{wire} 0")

    def write(self, path):
        with path.open("w") as out:
            out.write(f"p cnf {self.next_var - 1} {len(self.clauses) + len(self.xors)}\n")
            out.write("\n".join(self.clauses))
            out.write("\n")
            out.write("\n".join(self.xors))
            out.write("\n")



def s3(circuit, a, b, c):
    """Koblitz b=1 S3: e2^2 + e3 + 1 = 0."""
    ab = circuit.mul(a, b)
    e2 = circuit.add(ab, circuit.add(circuit.mul(a, c), circuit.mul(b, c)))
    e3 = circuit.mul(ab, c)
    circuit.require_zero(circuit.add(circuit.add(circuit.square(e2), e3),
                                     circuit.constant(1)))
