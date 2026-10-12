"""Count every public Onb arithmetic/conversion method entry in one solve.

The count boundary is the Python field API. Calls made through `self` by
inherited methods are counted too; bit operations inside a method are not.
"""

from field import Onb


class CountedOnb(Onb):
    NAMES = ('fromCoords', 'toCoords', 'add', 'mul', 'sqr', 'frob',
             'inv', 'trace', 'one', 'zero', 'pow')

    def __init__(self, m):
        super().__init__(m)
        self.calls = {name: 0 for name in self.NAMES}

    def reset_counts(self):
        for name in self.NAMES:
            self.calls[name] = 0

    def snapshot_counts(self):
        return dict(self.calls)

    def fromCoords(self, a):
        self.calls['fromCoords'] += 1
        return super().fromCoords(a)

    def toCoords(self, a):
        self.calls['toCoords'] += 1
        return super().toCoords(a)

    def add(self, a, b):
        self.calls['add'] += 1
        return super().add(a, b)

    def mul(self, a, b):
        self.calls['mul'] += 1
        return super().mul(a, b)

    def sqr(self, a):
        self.calls['sqr'] += 1
        return super().sqr(a)

    def frob(self, a, k):
        self.calls['frob'] += 1
        return super().frob(a, k)

    def inv(self, a):
        self.calls['inv'] += 1
        return super().inv(a)

    def trace(self, a):
        self.calls['trace'] += 1
        return super().trace(a)

    def one(self):
        self.calls['one'] += 1
        return super().one()

    def zero(self):
        self.calls['zero'] += 1
        return super().zero()

    def pow(self, a, e):
        self.calls['pow'] += 1
        return super().pow(a, e)
