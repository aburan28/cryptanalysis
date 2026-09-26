"""Independent Python recurrence for the native synthetic Metal walker."""
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research' / 'step_table'))
import pack
import table
from curves import CurvePb
from field import Pb

POLY = (1 << 131) | (1 << 13) | 7
STATE = struct.Struct('<14I7Q')
REPORT = struct.Struct('<3Q14I')
MASK = (1 << 64) - 1
TRACE = 0x74726163652d7631
DPHASH = 0x64702d6576656e74
NONE = 0xffffffff


def words(value):
    return [(value >> (32 * i)) & 0xffffffff for i in range(5)]


def xy(point):
    return [0] * 10 if point is None else words(point[0]) + words(point[1])


def decode(raw):
    w = struct.unpack('<9I', raw)
    if w == (0,) * 8 + (0x80000000,):
        return None
    if w[8] & ~63:
        raise ValueError('invalid packed point')
    return (sum(w[i] << (32 * i) for i in range(4)) | ((w[8] & 7) << 128),
            sum(w[4 + i] << (32 * i) for i in range(4)) | ((w[8] >> 3) << 128))


class Reference:
    def __init__(self, directions, branches):
        self.field = Pb(131, POLY)
        self.curve = CurvePb(self.field)
        self.selector = table.Selector(131)
        self.toOnb = pack.columns((ROOT / 'generated/eccF131.h').read_text(), 'Z_TO_ONB')
        self.cyclicColumns = [self.selector.cyclic(v) for v in self.toOnb]
        self.branches = branches
        if len(directions) != 262 * branches * 36:
            raise ValueError('wrong signed direction count')
        self.points = [decode(directions[i:i + 36]) for i in range(0, len(directions), 36)]
        if any(p is None for p in self.points):
            raise ValueError('source directions must be finite')

    def constants(self):
        out = []
        for nibble in range(33):
            for value in range(16):
                value = (value << (4 * nibble)) & ((1 << 131) - 1)
                out.extend(words(pack.linear(value, self.cyclicColumns)))
        for pivot in range(131):
            row = sum(((column >> pivot) & 1) << bit for bit, column in enumerate(self.cyclicColumns))
            out.extend(words(row))
        out.extend(pow(w, -1, 131) if w % 131 else 0 for w in range(132))
        result = struct.pack('<%dI' % len(out), *out)
        assert len(result) == 13708
        return result

    def initial(self, seed):
        return {'point': None, 'history': [NONE] * 3, 'mode': 1, 'seed': seed,
                'trailSteps': 0, 'walkSteps': 0, 'reseeds': 0, 'trace': TRACE, 'dpHash': DPHASH, 'dpCount': 0}

    @staticmethod
    def serialize(state):
        values = xy(state['point']) + state['history'] + [state['mode']]
        values += [state[name] for name in ('seed', 'trailSteps', 'walkSteps', 'reseeds', 'trace', 'dpHash', 'dpCount')]
        return STATE.pack(*values)

    @staticmethod
    def deserialize(raw):
        values = STATE.unpack(raw)
        point = (sum(values[i] << (32 * i) for i in range(5)),
                 sum(values[5 + i] << (32 * i) for i in range(5)))
        return {'point': point, 'history': list(values[10:13]), 'mode': values[13],
                **dict(zip(('seed', 'trailSteps', 'walkSteps', 'reseeds', 'trace', 'dpHash', 'dpCount'),
                           values[14:]))}

    def seed_point(self, seed):
        n = len(self.points)
        u = table.mix64(seed ^ 0x736565642d616464) % n
        v = table.mix64(seed ^ 0x736565642d706169) % n
        if v == (u ^ 1):
            v = (v + 2) % n
        return self.curve.add(self.points[u], self.points[v])

    def tag(self, point, history):
        x, y = [pack.linear(v, self.toOnb) for v in point]
        h, k, eps = self.selector.tag(x, y, self.branches, salt=20260921)
        d = 2 * (k * self.branches + h) + eps
        def fruitless(value):
            return (value ^ history[0]) == 1 or ((value ^ history[1]) == 1 and (history[0] ^ history[2]) == 1)
        for _ in range(self.branches):
            if not fruitless(d):
                return d
            h = (h + 1) % self.branches
            d = 2 * (k * self.branches + h) + eps
        raise ValueError('cycle rule exhausted')

    def cycle(self, state, lane, lanes, dp_weight, seed_stride=None):
        record = None
        seed_stride = lanes if seed_stride is None else seed_stride
        if state['mode'] >= 2:
            return record
        if state['mode'] == 0:
            p = state['point']
            weight = 0 if p is None else table.popcount(pack.linear(p[0], self.toOnb))
            if weight in (0, 131):
                state['mode'] = 2
                return record
            if 0 <= weight <= dp_weight:
                record = REPORT.pack(state['seed'], state['trailSteps'], lane, *xy(p), *state['history'], 0)
                for word in xy(p) + state['history']:
                    state['dpHash'] = table.mix64(state['dpHash'] ^ word)
                state['dpHash'] = table.mix64(state['dpHash'] ^ state['trailSteps'] ^ state['seed'])
                state['dpCount'] += 1
                if state['seed'] > MASK - seed_stride:
                    state['mode'] = 3
                    return record
                state['seed'] += seed_stride
                state['mode'] = 1
            else:
                tag = self.tag(p, state['history'])
                state['history'] = [tag] + state['history'][:2]
                state['point'] = self.curve.add(p, self.points[tag])
                state['walkSteps'] += 1
                state['trailSteps'] += 1
                state['trace'] = table.mix64(state['trace'] ^ (tag << 32) ^ state['walkSteps'])
                if state['point'] is None:
                    state['mode'] = 2
                return record
        if state['mode'] == 1:
            state['point'] = self.seed_point(state['seed'])
            state['history'] = [NONE] * 3
            state['trailSteps'] = 0
            state['reseeds'] += 1
            state['mode'] = 0 if state['point'] is not None else 2
        return record

    def replay(self, lane, lanes, seed, cycles, dp_weight, seed_stride=None):
        state = self.initial(seed + lane)
        return self.replay_from(self.serialize(state), lane, lanes, cycles,
                                dp_weight, seed_stride)

    def replay_from(self, raw, lane, lanes, cycles, dp_weight, seed_stride=None):
        state = self.deserialize(raw)
        records = []
        for _ in range(cycles):
            record = self.cycle(state, lane, lanes, dp_weight, seed_stride)
            if record is not None:
                records.append(record)
        return self.serialize(state), records
