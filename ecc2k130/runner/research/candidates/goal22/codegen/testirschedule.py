# Tests for the emission scheduler in ir.Prog.  See HOST-SCHEDULE.md.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import unittest

import build
import ir


def polyMulProg(n, cut):
    p = ir.Prog()
    a = [p.addInput('a', i) for i in range(n)]
    b = [p.addInput('b', i) for i in range(n)]
    r = build.polyMulIr(p, a, b, cut)
    p.fuseLop3(r)
    return p, r


def toOnbProg(m):
    p = ir.Prog()
    h = [p.addInput('h', i) for i in range(2 * m - 1)]
    r = build.toOnbIr(p, h, m)
    p.fuseLop3(r)
    return p, r


class SlotCountTests(unittest.TestCase):
    """slotCount is the pass's scoring function, so it has to be exactly what
    emit() allocates -- a score that disagreed with the emitter would pick the
    wrong order."""

    def check(self, p, r):
        for order in (p.emitOrder(r), p.suOrder(r)):
            p.schedule, p.scheduleKey = order, tuple(r)
            unused, slots = p.emit(r, 'o')
            self.assertEqual(slots, p.slotCount(r, order))

    def test_agrees_with_the_emitter_on_a_leaf(self):
        p, r = polyMulProg(12, 6)
        self.check(p, r)

    def test_agrees_with_the_emitter_on_a_conversion(self):
        p, r = toOnbProg(23)
        self.check(p, r)


class ScheduleTests(unittest.TestCase):
    def orders(self):
        out = []
        p, r = polyMulProg(12, 6)
        out.append(('polyMul', p, r))
        p, r = toOnbProg(23)
        out.append(('toOnb', p, r))
        return out

    def test_schedule_is_a_topological_order_of_every_live_operation(self):
        for name, p, r in self.orders():
            p.scheduleLive(r)
            seen = set()
            for i in p.schedule:
                for a in p.ops[i][1]:
                    if p.inputRef[a] is None:
                        self.assertIn(a, seen, '%s: operand emitted late' % name)
                seen.add(i)
            p.schedule, p.scheduleKey = None, None
            self.assertEqual(sorted(seen), sorted(p.emitOrder(r)),
                             '%s: schedule dropped or invented operations' % name)

    def test_scheduling_never_costs_more_slots_than_construction_order(self):
        for name, p, r in self.orders():
            before = p.slotCount(r, p.emitOrder(r))
            p.scheduleLive(r)
            after = p.slotCount(r, p.schedule)
            self.assertLessEqual(after, before, name)

    def test_scheduling_does_not_change_the_operation_count(self):
        for name, p, r in self.orders():
            before = p.instrCount(r)
            p.scheduleLive(r)
            self.assertEqual(p.instrCount(r), before, name)
            self.assertEqual(len(p.schedule), before, name)

    def test_the_conversion_is_where_the_pass_pays(self):
        # toOnb is a forest of independent output accumulations, which is the
        # shape Sethi-Ullman order is for; the m=131 numbers are in
        # HOST-SCHEDULE.md.
        p, r = toOnbProg(23)
        before = p.slotCount(r, p.emitOrder(r))
        p.scheduleLive(r)
        self.assertLess(p.slotCount(r, p.schedule), before)

    def test_emitted_source_changes_but_stays_the_same_length(self):
        p, r = toOnbProg(23)
        plain, plainSlots = p.emit(r, 'o')
        p.scheduleLive(r)
        sched, schedSlots = p.emit(r, 'o')
        self.assertEqual(len(plain), len(sched))
        self.assertNotEqual(plain, sched)
        self.assertLess(schedSlots, plainSlots)


class EvaluationTests(unittest.TestCase):
    """The schedule reorders emission only; the DAG and therefore the value of
    every root is untouched."""

    def test_roots_evaluate_the_same_before_and_after(self):
        p, r = polyMulProg(12, 6)
        vals = {}
        for i in range(12):
            vals[('a', i)] = 0x5A5A5A5A ^ (i * 2654435761)
            vals[('b', i)] = 0xC3C3C3C3 ^ (i * 40503)
        before = p.evaluate(vals, r)
        p.scheduleLive(r)
        self.assertEqual(p.evaluate(vals, r), before)


if __name__ == '__main__':
    unittest.main()
