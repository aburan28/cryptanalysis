"""Exact target-derived residual domain for the last fixed-sum pair block."""


def build(field, curve, geometry, q, raw_targets):
    entries = []
    last_states = geometry["blocks"][5]["states"]
    for target_index, raw_target in enumerate(raw_targets):
        if curve.mul(4, raw_target) != q:
            raise ValueError("raw target preimage failed subgroup projection")
        for state_index, state in enumerate(last_states):
            last = tuple(state["raw_sum"])
            residual = curve.add(raw_target, curve.neg(last))
            if residual is None or residual[0] == 1:
                continue
            if curve.add(residual, last) != raw_target:
                raise ValueError("target-dependent residual failed group replay")
            w = field.inv(residual[0] ^ 1)
            entries.append({"w_phi": w, "residual_point": list(residual),
                            "raw_target_index": target_index,
                            "last_state_index": state_index,
                            "last_columns": state["columns"]})
    if len(entries) != 640 or len({e["w_phi"] for e in entries}) != 640:
        raise ValueError("frozen N41 backward residual domain changed")
    return entries
