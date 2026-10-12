#!/usr/bin/env python3
"""Bounded carry-aware digit search over the fixed dual-orbit seed set."""

from collections import Counter
from functools import lru_cache
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DUAL = ROOT / "prime-j0-dual-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("carry_dual", DUAL / "screen.py")
dual = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dual)
SOURCE = DUAL / "cover-priority-rho0.bin"
PANEL = ROOT / "prime-j0-adic-orbit-20261011/fresh-inputs.json"


def digest(raw):
    return sha256(raw).hexdigest()


def load_cover():
    raw = SOURCE.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    assert len(raw) == 20 + 4 * classes + 4 * count
    assignments = [divmod(value, 16) for (value,) in
                   struct.iter_unpack("<I", raw[20:20 + 4 * classes])]
    seeds = list(struct.iter_unpack("<hh", raw[20 + 4 * classes:]))
    assert seeds[0] == (0, 0)
    return raw, assignments, seeds


def offer_index(seeds, canonical, nodes):
    node_index = {node: index for index, node in enumerate(nodes)}
    providers = [[] for _ in nodes]
    for seed_id, seed in enumerate(seeds):
        for map_id in range(4):
            digit = dual.mapped(seed, map_id)
            if dual.screen.norm(digit) > dual.NORM_LIMIT:
                continue
            node = canonical[dual.screen.index(digit, dual.RADIX)]
            providers[node_index[node]].append((seed_id, map_id, digit))
    assert all(providers)
    return node_index, providers


def make_options(canonical, node_index, providers):
    @lru_cache(maxsize=262_144)
    def options(ra, rb):
        node = canonical[ra * dual.RADIX + rb]
        out = []
        for seed_id, map_id, base_digit in providers[node_index[node]]:
            for unit_code, digit in enumerate(dual.screen.units(base_digit)):
                if digit[0] % dual.RADIX == ra and digit[1] % dual.RADIX == rb:
                    out.append((digit[0], digit[1], seed_id, map_id, unit_code))
        assert out
        return tuple(out)
    return options


def rank(state):
    a, b, rho, terms, path = state
    return (rho != 0, rho, terms, dual.screen.norm((a, b)), path)


def replay(scalar, assignments, seeds, canonical, node_index, options, beam_width):
    original = dual.screen.representative(scalar % dual.screen.ORDER)
    assert (original[0] + original[1] * dual.LAMBDA_TAU - scalar) % \
        dual.screen.ORDER == 0
    states = [(original[0], original[1], 0, 0, ())]
    examined = expanded = 0
    for window in range(dual.WINDOWS):
        next_states = {}
        for a, b, rho, terms, path in states:
            choices = options(a % dual.RADIX, b % dual.RADIX)
            examined += len(choices)
            for da, db, seed_id, map_id, unit in choices:
                assert (a - da) % dual.RADIX == (b - db) % dual.RADIX == 0
                na, nb = (a - da) // dual.RADIX, (b - db) // dual.RADIX
                new_state = (na, nb, rho + int(seed_id != 0 and map_id == 3),
                             terms + int(seed_id != 0),
                             path + ((da, db, seed_id, map_id, unit),))
                key = (na, nb, rho + int(seed_id != 0 and map_id == 3))
                old = next_states.get(key)
                if old is None or rank(new_state) < rank(old):
                    next_states[key] = new_state
                expanded += 1
        states = sorted(next_states.values(), key=rank)[:beam_width]
        assert states, (scalar, window)
    admissible = [state for state in states if
                  dual.screen.norm(state[:2]) < dual.TERMINAL_BOUND ** 2]
    candidate = min(admissible, key=rank) if admissible else None

    a, b = original
    fixed_path = []
    fixed_rho = fixed_terms = 0
    for _ in range(dual.WINDOWS):
        class_index = node_index[canonical[a % dual.RADIX * dual.RADIX +
                                           b % dual.RADIX]]
        seed_id, map_id = assignments[class_index]
        matches = [row for row in options(a % dual.RADIX, b % dual.RADIX)
                   if row[2:4] == (seed_id, map_id)]
        assert matches
        row = matches[0]
        fixed_path.append(row)
        a, b = (a - row[0]) // dual.RADIX, (b - row[1]) // dual.RADIX
        fixed_rho += int(seed_id != 0 and map_id == 3)
        fixed_terms += int(seed_id != 0)
    fixed = (a, b, fixed_rho, fixed_terms, tuple(fixed_path))
    assert dual.screen.norm(fixed[:2]) < dual.TERMINAL_BOUND ** 2
    selected = min((fixed, candidate), key=rank) if candidate else fixed
    place = 1
    reconstructed = [0, 0]
    for da, db, _, _, _ in selected[4]:
        reconstructed[0] += place * da
        reconstructed[1] += place * db
        place *= dual.RADIX
    reconstructed[0] += place * selected[0]
    reconstructed[1] += place * selected[1]
    assert tuple(reconstructed) == original
    return fixed, selected, examined, expanded, candidate is None


def summarize(states):
    rho = sum(state[2] for state in states)
    terms = sum(state[3] for state in states)
    active = sum(state[2] != 0 for state in states)
    return {"active_rho_cases": active, "rho_terms": rho,
            "nonzero_full_window_terms": terms,
            "max_terminal_norm": max(dual.screen.norm(state[:2]) for state in states)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beam-width", type=int, default=8)
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--output-prefix", default="design")
    parser.add_argument("--certificate", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.beam_width <= 32
    raw, assignments, seeds = load_cover()
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index, providers = offer_index(seeds, canonical, nodes)
    options = make_options(canonical, node_index, providers)
    input_raw = args.panel.read_bytes()
    scalars = [int(value, 16) for value in json.loads(input_raw)["scalars_hex"]]
    assert len(scalars) == 4096
    fixed = []
    selected = []
    examined = expanded = fallbacks = 0
    option_counts = Counter(len(row) for row in providers)
    certificate_lines = []
    for index, scalar in enumerate(scalars):
        a, b, seen, made, fallback = replay(
            scalar, assignments, seeds, canonical, node_index, options,
            args.beam_width)
        fixed.append(a)
        selected.append(b)
        if args.certificate:
            certificate_lines.append(json.dumps(
                {"index": index, "terminal": b[:2], "digits": b[4]},
                separators=(",", ":")))
        examined += seen
        expanded += made
        fallbacks += fallback
        if (index + 1) % 512 == 0:
            print(f"screened {index + 1}/{len(scalars)}", flush=True)
    result = {"schema": 1, "status": "design_screen",
              "beam_width": args.beam_width,
              "source_sha256": digest(Path(__file__).read_bytes()),
              "cover_sha256": digest(raw), "input_sha256": digest(input_raw),
              "cases": len(scalars), "seed_count": len(seeds),
              "classes_with_alternatives": sum(n > 1 for n in map(len, providers)),
              "class_offer_histogram": dict(sorted(option_counts.items())),
              "fixed": summarize(fixed), "carry_aware": summarize(selected),
              "examined_offers": examined, "expanded_states": expanded,
              "terminal_fallback_cases": fallbacks,
              "option_cache": options.cache_info()._asdict()}
    if args.certificate:
        certificate = HERE / f"{args.output_prefix}-paths-width{args.beam_width}.jsonl"
        certificate.write_text("\n".join(certificate_lines) + "\n")
        result["certificate_sha256"] = digest(certificate.read_bytes())
    output = HERE / f"{args.output_prefix}-screen-width{args.beam_width}.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
