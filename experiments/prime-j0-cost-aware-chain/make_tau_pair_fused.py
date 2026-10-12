#!/usr/bin/env python3
"""Generate a shortest-path tau-pair policy using 121 prepared unit-orbit points."""

import argparse
import hashlib
from heapq import heappop, heappush
from pathlib import Path

from make_tau_tail_double import BOUND, INF, PHASES, SIDE, DIGITS, choices_for_phase
from make_tau_tail_double import generate as unfused_generate, index, tau2
from make_tau_tail_double_fold import HALF, half_index, representative as half_representative
from make_tau_tail_gate import canonical_cost
from run import SEEDS, TABLE


ZERO = 1023
UNREACHABLE = 1022
ONE_ADD_REPS = set(SEEDS) | {(-3 * b, a + 3 * b) for a, b in SEEDS}


def omega(a, b):
    return a + 3 * b, -a - 2 * b


def tau(a, b):
    return -3 * b, a + 3 * b


def orbit(z):
    a, b = z
    members = set()
    for _ in range(3):
        members.update(((a, b), (-a, -b)))
        a, b = omega(a, b)
    return members


def point_representative(z):
    members = orbit(z)
    one_add = members.intersection(ONE_ADD_REPS)
    assert len(one_add) <= 1
    return next(iter(one_add)) if one_add else min(members)


def encode(orbit_id, power, sign):
    assert 0 <= orbit_id < 121 and 0 <= power < 3 and sign in (-1, 1)
    return orbit_id | (power << 7) | ((sign < 0) << 9)


def decode(word, representatives):
    if word == ZERO:
        return 0, 0
    assert word != UNREACHABLE
    orbit_id, power, sign = word & 127, (word >> 7) & 3, -1 if word & 512 else 1
    a, b = representatives[orbit_id]
    for _ in range(power):
        a, b = omega(a, b)
    return sign * a, sign * b


def catalog():
    realization = {(a, b): (even, odd)
                   for a, b, _cost, even, odd in choices_for_phase(0)}
    contributions = set(realization)
    assert len(contributions) == 727 and (0, 0) in contributions
    reps = sorted({point_representative(z) for z in contributions if z != (0, 0)})
    assert len(reps) == 121 and len(ONE_ADD_REPS) == 18
    words = {}
    for orbit_id, rep in enumerate(reps):
        a, b = rep
        for power in range(3):
            for sign in (-1, 1):
                point = sign * a, sign * b
                assert point not in words
                words[point] = encode(orbit_id, power, sign)
            a, b = omega(a, b)
    assert set(words) == contributions - {(0, 0)}
    words[(0, 0)] = ZERO
    recipes = [realization[rep] for rep in reps]
    assert sum((even != 255) + (odd != 255) == 1 for even, odd in recipes) == 18
    even_words = [UNREACHABLE] * 81
    odd_words = [UNREACHABLE] * 81
    for slot, digit in DIGITS:
        a, b = digit[:2]
        even_words[slot] = words[a, b]
        odd_words[slot] = words[tau(a, b)]
        for phase in range(PHASES):
            assert ((((even_words[slot] >> 7) & 3) + phase) % 3 != 0) == (
                (digit[3] + phase) % 3 != 0)
            assert ((((odd_words[slot] >> 7) & 3) + phase) % 3 != 0) == (
                (digit[3] + phase) % 3 != 0)
    return reps, recipes, words, even_words, odd_words


def transition(a, b, word, reps):
    da, db = decode(word, reps)
    ax, by = a - da, b - db
    assert ax % 3 == by % 3 == 0
    return 2 * (ax // 3) + by, -(ax + by) // 3


def generate(reps, words):
    costs = [INF] * (PHASES * SIDE * SIDE)
    actions = [None] * len(costs)
    heap = []
    for phase in range(PHASES):
        pos = index(0, 0, phase)
        costs[pos], actions[pos] = 0, ZERO
        heappush(heap, (0, 0, 0, phase))
    options = []
    for phase in range(PHASES):
        row = []
        for (da, db), word in sorted(words.items()):
            digit_cost = 0 if word == ZERO else 16 + int(
                (((word >> 7) & 3) + phase) % 3 != 0)
            row.append((da, db, digit_cost, word))
        options.append(row)
    while heap:
        cost, qa, qb, next_phase = heappop(heap)
        if cost != costs[index(qa, qb, next_phase)]:
            continue
        phase = (next_phase - 1) % PHASES
        base_a, base_b = tau2(qa, qb)
        for da, db, digit_cost, word in options[phase]:
            a, b = base_a + da, base_b + db
            if not (-BOUND <= a <= BOUND and -BOUND <= b <= BOUND) or (a, b) == (0, 0):
                continue
            new = cost + digit_cost + (10 if (qa, qb) != (0, 0) else 0)
            pos = index(a, b, phase)
            if new < costs[pos] or (new == costs[pos] and word < actions[pos]):
                costs[pos], actions[pos] = new, word
                heappush(heap, (new, a, b, phase))
    old_costs, _ = unfused_generate()
    assert all(new <= old for new, old in zip(costs, old_costs))
    return costs, actions, old_costs


def validate(costs, actions, reps):
    reached = paths = max_pairs = 0
    for phase in range(PHASES):
        for a in range(-BOUND, BOUND + 1):
            for b in range(-BOUND, BOUND + 1):
                pos = index(a, b, phase)
                if actions[pos] is None:
                    assert costs[pos] == INF
                    continue
                reached += 1
                x, y, p, steps = a, b, phase, 0
                while (x, y) != (0, 0):
                    old = index(x, y, p)
                    word = actions[old]
                    qx, qy = transition(x, y, word, reps)
                    assert -BOUND <= qx <= BOUND and -BOUND <= qy <= BOUND
                    new = index(qx, qy, (p + 1) % PHASES)
                    edge = (0 if word == ZERO else 16 + int(
                        (((word >> 7) & 3) + p) % 3 != 0))
                    edge += 10 if (qx, qy) != (0, 0) else 0
                    assert costs[old] == edge + costs[new]
                    assert costs[new] < costs[old]
                    x, y, p, steps = qx, qy, (p + 1) % PHASES, steps + 1
                    assert steps <= 256
                paths += steps
                max_pairs = max(max_pairs, steps)
    return reached, paths, max_pairs


def pack(costs, actions, reps):
    local = [[set() for _ in range(9)] for _ in range(PHASES)]
    gate = bytearray((PHASES * HALF + 7) // 8)
    for phase in range(PHASES):
        for a in range(BOUND + 1):
            for b in range(-BOUND if a else 0, BOUND + 1):
                full, mirror = index(a, b, phase), index(-a, -b, phase)
                assert costs[full] == costs[mirror]
                word = actions[full] if actions[full] is not None else UNREACHABLE
                local[phase][(a % 3) * 3 + b % 3].add(word)
                chosen = (actions[full] is not None and
                          costs[full] < canonical_cost(a, b, phase))
                mirror_chosen = (actions[mirror] is not None and
                                 costs[mirror] < canonical_cost(-a, -b, phase))
                assert chosen == mirror_chosen
                if chosen:
                    pos = phase * HALF + half_index(a, b)
                    gate[pos >> 3] |= 1 << (pos & 7)
    dictionary, offsets, lengths, encoders = [], [], [], []
    for phase in range(PHASES):
        phase_offsets, phase_lengths, phase_encoders = [], [], []
        for residue in range(9):
            group = sorted(local[phase][residue])
            assert len(group) <= 255
            phase_offsets.append(len(dictionary))
            phase_lengths.append(len(group))
            phase_encoders.append({word: code for code, word in enumerate(group)})
            dictionary.extend(group)
        offsets.append(phase_offsets)
        lengths.append(phase_lengths)
        encoders.append(phase_encoders)
    codes = bytearray(PHASES * HALF)
    for phase in range(PHASES):
        for a in range(BOUND + 1):
            for b in range(-BOUND if a else 0, BOUND + 1):
                full = index(a, b, phase)
                word = actions[full] if actions[full] is not None else UNREACHABLE
                pos = phase * HALF + half_index(a, b)
                codes[pos] = encoders[phase][(a % 3) * 3 + b % 3][word]
    for phase in range(PHASES):
        for a in range(-BOUND, BOUND + 1):
            for b in range(-BOUND, BOUND + 1):
                ra, rb, negative = half_representative(a, b)
                pos = phase * HALF + half_index(ra, rb)
                residue = (ra % 3) * 3 + rb % 3
                code = codes[pos]
                assert code < lengths[phase][residue]
                word = dictionary[offsets[phase][residue] + code]
                if negative and word not in (ZERO, UNREACHABLE):
                    word ^= 512
                full = index(a, b, phase)
                assert bool(gate[pos >> 3] & (1 << (pos & 7))) == (
                    actions[full] is not None and costs[full] < canonical_cost(a, b, phase))
                if word == UNREACHABLE:
                    assert actions[full] is None
                    continue
                if (a, b) == (0, 0):
                    assert word == ZERO
                    continue
                qx, qy = transition(a, b, word, reps)
                next_cost = costs[index(qx, qy, (phase + 1) % PHASES)]
                edge = (0 if word == ZERO else 16 + int(
                    (((word >> 7) & 3) + phase) % 3 != 0))
                edge += 10 if (qx, qy) != (0, 0) else 0
                assert costs[full] == edge + next_cost and next_cost < costs[full]
    return bytes(codes), bytes(gate), offsets, lengths, dictionary


def render(reps, recipes, even_words, odd_words, codes, gate, offsets, lengths, dictionary):
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    lines = ["/* Generated by make_tau_pair_fused.py; do not edit.",
             f" * Generator SHA-256: {source_hash}",
             " * Pair word: orbit bits 0..6, omega power bits 7..8, sign bit 9.",
             " * 1023 = zero contribution; 1022 = unreachable.",
             " */", "#ifndef CA_TAU_PAIR_FUSED_H", "#define CA_TAU_PAIR_FUSED_H",
             "#include <stdint.h>", f"#define CA_TAU_PAIR_FUSED_REPS {len(reps)}",
             f"#define CA_TAU_PAIR_FUSED_HALF {HALF}",
             "#define CA_TAU_PAIR_FUSED_ZERO 1023",
             "#define CA_TAU_PAIR_FUSED_UNREACHABLE 1022"]

    def array(name, ctype, values, width=20):
        lines.append(f"static const {ctype} ca_tau_pair_fused_{name}[{len(values)}] = {{")
        for offset in range(0, len(values), width):
            lines.append("    " + ", ".join(map(str, values[offset:offset + width])) + ",")
        lines.append("};")

    for name, values, ctype in (
            ("code", codes, "uint8_t"), ("gate", gate, "uint8_t"),
            ("dictionary", dictionary, "uint16_t"),
            ("rep_a", [a for a, _b in reps], "int16_t"),
            ("rep_b", [b for _a, b in reps], "int16_t"),
            ("rep_even", [e for e, _o in recipes], "uint8_t"),
            ("rep_odd", [o for _e, o in recipes], "uint8_t"),
            ("even_word", even_words, "uint16_t"),
            ("odd_word", odd_words, "uint16_t")):
        array(name, ctype, values)
    for name, values, ctype in (("offset", offsets, "uint16_t"),
                                ("length", lengths, "uint8_t")):
        lines.append(f"static const {ctype} ca_tau_pair_fused_{name}[{PHASES}][9] = {{")
        for row in values:
            lines.append("    {" + ", ".join(map(str, row)) + "},")
        lines.append("};")
    lines.extend(["#endif", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] /
                        "src/generated/tau_pair_fused.h")
    args = parser.parse_args()
    reps, recipes, words, even_words, odd_words = catalog()
    costs, actions, old_costs = generate(reps, words)
    reached, paths, max_pairs = validate(costs, actions, reps)
    codes, gate, offsets, lengths, dictionary = pack(costs, actions, reps)
    data = render(reps, recipes, even_words, odd_words, codes, gate, offsets, lengths,
                  dictionary)
    if args.output.exists() and args.output.read_text() != data:
        raise SystemExit(f"generated fused policy changed: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(data)
    static_bytes = (len(codes) + len(gate) + 2 * len(dictionary) +
                    len(reps) * (2 + 2 + 1 + 1) + 2 * len(even_words) + 2 * len(odd_words) +
                    3 * 9 * 3)
    print(f"orbits={len(reps)} reachable={reached} policy_path_steps={paths} "
          f"max_pairs={max_pairs} better_states={sum(a < b for a, b in zip(costs, old_costs))} "
          f"max_residue_dictionary={max(map(max, lengths))} "
          f"dictionary_entries={len(dictionary)} static_bytes={static_bytes} "
          f"header_sha256={hashlib.sha256(data.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
