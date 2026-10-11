"""Canonical signed-Frobenius orbits using cyclic ONB coordinates.

For a type-II optimal normal basis, squaring permutes the basis coordinates
in one cycle.  Compare rotations of that coordinate word, then transform the
winning point once.  The key order differs from canonical_x_first, so an
index must be built and queried with the same convention.
"""


class CycleCanonical:
    def __init__(self, onb):
        degree = onb.m
        order = []
        position = 1
        for _ in range(degree):
            folded = onb.fold(position)
            order.append(folded - 1)
            position = 2 * position % onb.n
        if len(set(order)) != degree:
            raise ValueError("Frobenius does not form one basis cycle")
        self.degree = degree
        self.mask = (1 << degree) - 1
        # Byte lookup tables perform the fixed coordinate permutation with
        # eleven table accesses for degree 83, rather than 83 field squarings.
        self.tables = []
        for offset in range(0, degree, 8):
            table = [0] * 256
            for byte in range(1, 256):
                bit = byte & -byte
                source = offset + bit.bit_length() - 1
                table[byte] = table[byte ^ bit]
                if source < degree:
                    table[byte] |= 1 << order.index(source)
            self.tables.append(tuple(table))

    def cycle_word(self, onb, value):
        coords = onb.toCoords(value)
        result = 0
        for table in self.tables:
            result |= table[coords & 255]
            coords >>= 8
        return result

    def canonical(self, curve, point, counts=None):
        if point is None:
            return (-1, -1), 0, 1
        onb = getattr(curve, "curve", curve).f
        if onb.m != self.degree:
            raise ValueError("field degree differs from cycle map")
        xword = self.cycle_word(onb, point[0])
        best = xword
        shifts = [0]
        rotated = xword
        for shift in range(1, self.degree):
            rotated = ((rotated << 1) | (rotated >> (self.degree - 1))) & self.mask
            if rotated < best:
                best, shifts = rotated, [shift]
            elif rotated == best:
                shifts.append(shift)
        if counts is not None:
            counts["word_rotations"] = counts.get("word_rotations", 0) + self.degree - 1
            counts["coordinate_permutations"] = counts.get("coordinate_permutations", 0) + 1
        answer = None
        for shift in shifts:
            transformed = (point if shift == 0 else
                           (onb.frob(point[0], shift), onb.frob(point[1], shift)))
            if counts is not None and shift:
                counts["selected_field_frobenius"] = counts.get("selected_field_frobenius", 0) + 2
            x, y = transformed
            negative_y = onb.add(x, y)
            sign = 1 if y <= negative_y else -1
            key = (x, min(y, negative_y))
            candidate = (self.cycle_word(onb, x), key[1], key, shift, sign)
            if answer is None or candidate[:2] < answer[:2]:
                answer = candidate
        return answer[2], answer[3], answer[4]
