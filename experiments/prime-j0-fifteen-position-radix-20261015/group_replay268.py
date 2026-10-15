#!/usr/bin/env python3
"""Independent affine secp256k1 replay of the 15-position 268-tau format."""
from hashlib import sha256
import json
from pathlib import Path
import screen268 as screen

HERE = Path(__file__).resolve().parent
reference = screen.nearest.model.reference
canonical, encode = screen.orbit.canonical, screen.orbit.encode


def main():
    digits = screen.digits()
    seeds = sorted({canonical(pair) for pair in digits})
    seeds.remove((0,0))
    seeds.insert(0,(0,0))
    seed_index = {pair:index for index,pair in enumerate(seeds)}
    codes = [(seed_index[canonical(pair)],*encode(pair,canonical(pair)))
             for pair in digits]
    source = screen.EXPERIMENTS / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(source.read_text())['cases']
    order = screen.nearest.model.mixed.screen.ORDER
    fresh_seed = b'nearest-orbit-19183-fresh-v1'
    fresh = [int.from_bytes(sha256(fresh_seed+i.to_bytes(4,'big')).digest(),
                            'big')%order for i in range(256)]
    fresh += [0,1,order-1,1 << 255]
    scalars = [int(case['scalar_hex'],16)%order for case in cases]+fresh

    bases = []
    base = reference.G
    for _ in range(screen.STEPS):
        bases.append((base,reference.tau_point(base)))
        base = reference.add(reference.multiply(screen.T,base),
                             reference.negate(reference.tau_point(base)))
    terminal_base = (base,reference.tau_point(base))
    point_cache = {}
    terminal_cache = {}
    output_digest = sha256()
    nonzero = 0

    def seed_point(window,index):
        if index == 0:
            return None
        key = window,index
        if key not in point_cache:
            a,b = seeds[index]
            window_base,tau_base = bases[window]
            point_cache[key] = reference.add(reference.multiply(a,window_base),
                                              reference.multiply(b,tau_base))
        return point_cache[key]

    for scalar in scalars:
        state = screen.nearest.model.mixed.screen.representative(scalar)
        total = None
        for window in range(screen.STEPS):
            state,d = screen.step(state,digits)
            residue = (d[0]+screen.T*d[1])%screen.Q
            index,power,sign = codes[residue]
            assert d == digits[residue]
            total = reference.add(total,reference.unit_point(
                seed_point(window,index),2*power+sign))
            nonzero += int(index != 0)
        terminal_seed = canonical(state)
        power,sign = encode(state,terminal_seed)
        if terminal_seed != (0,0):
            if terminal_seed not in terminal_cache:
                a,b = terminal_seed
                terminal_cache[terminal_seed] = reference.add(
                    reference.multiply(a,terminal_base[0]),
                    reference.multiply(b,terminal_base[1]))
            total = reference.add(total,reference.unit_point(
                terminal_cache[terminal_seed],2*power+sign))
        assert total == reference.multiply(scalar,reference.G)
        if total is None:
            output_digest.update(bytes(64))
        else:
            output_digest.update(total[0].to_bytes(32,'big'))
            output_digest.update(total[1].to_bytes(32,'big'))
    baseline = json.loads((screen.PARENT / 'group-replay140.json').read_text())
    assert output_digest.hexdigest() == baseline['output_point_sha256']
    return {
        'schema':1,'radix':[screen.T,-1],'positions':screen.STEPS,
        'fixture_sha256':sha256(source.read_bytes()).hexdigest(),
        'frozen_case_count':len(cases),'fresh_case_count':len(fresh),
        'independent_scalar_replays':len(scalars),
        'nonzero_digit_addends':nonzero,
        'touched_digit_seed_points':len(point_cache),
        'touched_terminal_seed_points':len(terminal_cache),
        'output_point_sha256':output_digest.hexdigest(),
        'matches_previous_binary_replay_digest':True,
        'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(main(),sort_keys=True,indent=2))
