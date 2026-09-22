"""Exact two-step oracle for the synthetic signed-direction walk.

The oracle deliberately computes the intermediate point before selecting the
second direction. A pair-sum lookup then reconstructs the same endpoint from
the original point. This proves endpoint/history equivalence and exposes the
actual runtime charge: the exact selector still needs the first point addition.
"""
from copy import deepcopy
import hashlib
import struct

from artifact_reference import pack, table

RESULT = struct.Struct('<16I')


def pointWeight(reference, point):
    if point is None:
        return 0
    return table.popcount(pack.linear(point[0], reference.toOnb))


def ordinaryUpdate(reference, state):
    """Apply one non-DP walking update and return its selected direction."""
    if state['mode'] != 0 or state['point'] is None:
        raise ValueError('ordinary update requires a finite walking state')
    direction = reference.tag(state['point'], state['history'])
    state['history'] = [direction] + state['history'][:2]
    state['point'] = reference.curve.add(state['point'], reference.points[direction])
    state['walkSteps'] += 1
    state['trailSteps'] += 1
    state['trace'] = table.mix64(state['trace'] ^ (direction << 32) ^ state['walkSteps'])
    if state['point'] is None:
        state['mode'] = 2
    return direction


def exactPair(reference, rawState, pairLookup, dpWeight=-1, lane=0, lanes=1,
              seedStride=None):
    """Fuse two ordinary updates or return the exact reason fusion is unsafe.

    pairLookup(u, v) returns the precomputed point D[u] + D[v]. The returned
    state must match two calls to Reference.cycle byte-for-byte when fused is
    true. Distinguished intermediate points and exceptional fibers fall back;
    they must remain visible to a collection walk.
    """
    original = reference.deserialize(rawState)
    baseline = deepcopy(original)
    reports = []
    for _ in range(2):
        report = reference.cycle(baseline, lane, lanes, dpWeight, seedStride)
        if report is not None:
            reports.append(report)

    outcome = {'fused': False, 'state': reference.serialize(baseline),
               'reports': reports, 'runtimeAdditions': 0, 'pairLookups': 0,
               'logicalCycles': 2}
    if original['mode'] != 0 or original['point'] is None:
        outcome['reason'] = 'not-walking'
        return outcome
    weight0 = pointWeight(reference, original['point'])
    if weight0 in (0, 131):
        outcome['reason'] = 'exceptional-start'
        return outcome
    if 0 <= weight0 <= dpWeight:
        outcome['reason'] = 'distinguished-start'
        return outcome

    fused = deepcopy(original)
    startPoint = fused['point']
    first = ordinaryUpdate(reference, fused)
    if fused['mode'] != 0 or fused['point'] is None:
        outcome['reason'] = 'exceptional-intermediate'
        return outcome
    weight1 = pointWeight(reference, fused['point'])
    if weight1 in (0, 131):
        outcome['reason'] = 'exceptional-intermediate-selector'
        return outcome
    if 0 <= weight1 <= dpWeight:
        outcome['reason'] = 'distinguished-intermediate'
        return outcome

    second = reference.tag(fused['point'], fused['history'])
    pair = pairLookup(first, second)
    fused['history'] = [second] + fused['history'][:2]
    fused['point'] = reference.curve.add(startPoint, pair)
    fused['walkSteps'] += 1
    fused['trailSteps'] += 1
    fused['trace'] = table.mix64(fused['trace'] ^ (second << 32) ^ fused['walkSteps'])
    if fused['point'] is None:
        fused['mode'] = 2
    actual = reference.serialize(fused)
    expected = reference.serialize(baseline)
    if actual != expected or reports:
        raise ValueError('pair endpoint differs from two exact ordinary updates')
    outcome.update(fused=True, state=actual, reports=[], first=first,
                   second=second, pairIndex=pairIndex(first, second),
                   runtimeAdditions=2, pairLookups=1,
                   reason='exact-intermediate-selector')
    return outcome


def pairIndex(u, v):
    if u > v:
        u, v = v, u
    return v * (v + 1) // 2 + u


def resultBytes(reference, state, first, second):
    point = state['point']
    xy = [0] * 10 if point is None else [
        (point[axis] >> (32 * word)) & 0xffffffff
        for axis in range(2) for word in range(5)]
    return RESULT.pack(*(xy + state['history'] + [first, second, int(point is None)]))


def inputDigest(states):
    return hashlib.sha256(b''.join(states)).hexdigest()
