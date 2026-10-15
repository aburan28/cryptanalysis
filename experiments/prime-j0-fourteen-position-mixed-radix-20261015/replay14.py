#!/usr/bin/env python3
"""Independent integer and affine replay of the selected ordered radix."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
SCREEN = EXPERIMENTS / "prime-j0-fifteen-position-radix-20261015" / "screen268.py"
FRONTIER = EXPERIMENTS / "prime-j0-fifteen-position-radix-20261015" / "frontier15.py"


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parent = load("screen268", SCREEN)
    frontier = load("frontier15", FRONTIER)
    result = json.loads((HERE / "screen14.json").read_text())
    schedule = result["local_payload_minimum"]["schedule"]
    terminal_radius = result["local_payload_minimum"]["radius_sequence"][-1]
    assert len(schedule) == 14
    digit_sets = {}
    for t in set(schedule):
        q = t*t-3*t+3
        digit_sets[t] = [frontier.digit(t,q,r) for r in range(q)]

    fixture = EXPERIMENTS / "prime-j0-mixed640-materialized-tree-20261013" / "selective-holdout.json"
    cases = json.loads(fixture.read_text())["cases"]
    order = parent.nearest.model.mixed.screen.ORDER
    fresh_seed = b"ordered-prime-norm-14-replay-v1"
    fresh = [int.from_bytes(sha256(fresh_seed+i.to_bytes(4,"big")).digest(),"big")%order
             for i in range(32)]
    fresh += [0,1,order-1,1 << 255]
    scalars = [int(case["scalar_hex"],16)%order for case in cases]+fresh
    reference = parent.nearest.model.reference

    bases = []
    base = reference.G
    for t in schedule:
        bases.append((base,reference.tau_point(base)))
        base = reference.add(reference.multiply(t,base),
                             reference.negate(reference.tau_point(base)))
    terminal_base = (base,reference.tau_point(base))
    output_digest = sha256()
    max_terminal_norm = 0

    for scalar in scalars:
        initial = parent.nearest.model.mixed.screen.representative(scalar)
        state = initial
        trace = []
        total = None
        for i,t in enumerate(schedule):
            q = t*t-3*t+3
            a,b = state
            da,db = digit_sets[t][(a+t*b)%q]
            shifted_b = b-db
            quotient,remainder = divmod(a-da+t*shifted_b,q)
            assert remainder == 0
            next_state = ((t-3)*quotient-shifted_b,quotient)
            assert state == (da+t*next_state[0]+3*next_state[1],
                             db-next_state[0]+(t-3)*next_state[1])
            window_base,tau_base = bases[i]
            term = reference.add(reference.multiply(da,window_base),
                                 reference.multiply(db,tau_base))
            total = reference.add(total,term)
            trace.append((t,(da,db)))
            state = next_state
        max_terminal_norm = max(max_terminal_norm,frontier.norm(*state))
        assert frontier.norm(*state) < terminal_radius*terminal_radius
        tail = reference.add(reference.multiply(state[0],terminal_base[0]),
                             reference.multiply(state[1],terminal_base[1]))
        total = reference.add(total,tail)
        for t,(da,db) in reversed(trace):
            a,b = state
            state = (da+t*a+3*b,db-a+(t-3)*b)
        assert state == initial
        assert (state[0]+state[1]*reference.LAMBDA_TAU-scalar)%order == 0
        assert total == reference.multiply(scalar,reference.G)
        if total is None:
            output_digest.update(bytes(64))
        else:
            output_digest.update(total[0].to_bytes(32,"big"))
            output_digest.update(total[1].to_bytes(32,"big"))
    return {
        "schema":1,
        "schedule":schedule,
        "terminal_radius":terminal_radius,
        "max_replayed_terminal_norm":max_terminal_norm,
        "frozen_case_count":len(cases),
        "fresh_case_count":len(fresh),
        "independent_affine_scalar_replays":len(scalars),
        "output_point_sha256":output_digest.hexdigest(),
        "fixture_sha256":sha256(fixture.read_bytes()).hexdigest(),
        "screen_sha256":sha256((HERE / "screen14.json").read_bytes()).hexdigest(),
        "source_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(main(),sort_keys=True,indent=2))
