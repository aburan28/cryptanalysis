"""Recover the canonical ONB x coordinate from a packed signed-orbit key."""


class CanonicalXFromOrbitKey:
    def __init__(self, orbit):
        self.n = orbit.n
        self.mask = (1 << orbit.n) - 1
        self.tables = []
        for start in range(0, orbit.n, 8):
            table = [0] * 256
            for byte in range(1, 256):
                bit = byte & -byte
                position = start + bit.bit_length() - 1
                table[byte] = table[byte ^ bit]
                if position < orbit.n:
                    table[byte] |= 1 << orbit.coordinate_cycle[position]
            self.tables.append(tuple(table))
        self.tables = tuple(self.tables)

    def canonical_x(self, key):
        """Match min(toCoords(Frob^j(P.x))) across all n rotations."""
        assert 0 <= key < (1 << (2 * self.n))
        cycle_x = key >> self.n
        best = self.mask
        for _ in range(self.n):
            coordinates = 0
            for offset, table in enumerate(self.tables):
                coordinates |= table[(cycle_x >> (8 * offset)) & 255]
            if coordinates < best:
                best = coordinates
            cycle_x = ((cycle_x << 1) | (cycle_x >> (self.n - 1))) & self.mask
        return best
