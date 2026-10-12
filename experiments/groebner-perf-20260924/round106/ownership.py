"""Native-free physical ownership simulation, independent of polynomial arithmetic."""


def ownership(proof, *, enabled=True, policy=2):
    nodes, outputs = proof['nodes'], proof['outputs']
    uses = [0]*len(nodes)
    for i, node in enumerate(nodes):
        if node[0] == 'mul':
            assert 0 <= node[1] < i
            uses[node[1]] += 1
        elif node[0] == 'xor':
            assert 0 <= node[1] < i and 0 <= node[2] < i
            uses[node[1]] += 1
            uses[node[2]] += 1
        else:
            assert node[0] == 'input'
    for i in outputs:
        assert 0 <= i < len(nodes)
        uses[i] += 1
    owned = [False]*len(nodes)
    live = peak = allocations = releases = left = right = checks = 0

    def consume(i):
        nonlocal live, releases
        assert uses[i] > 0
        uses[i] -= 1
        if not uses[i] and owned[i]:
            owned[i] = False
            live -= 1
            releases += 1

    for i, node in enumerate(nodes):
        donor = None
        if enabled and policy and node[0] == 'xor' and node[1] != node[2]:
            checks += 1
            if uses[node[1]] == 1:
                donor = node[1]
                left += 1
            elif uses[node[2]] == 1:
                donor = node[2]
                right += 1
        if donor is None:
            allocations += 1
            live += 1
        else:
            assert owned[donor]
            owned[donor] = False
        owned[i] = True
        peak = max(peak, live)
        if policy:
            if node[0] == 'mul':
                consume(node[1])
            elif node[0] == 'xor':
                consume(node[1])
                consume(node[2])
            if not uses[i]:
                assert owned[i]
                owned[i] = False
                live -= 1
                releases += 1
    if policy:
        for i in outputs:
            consume(i)
        assert live == 0 and not any(owned) and not any(uses)
    else:
        releases += live  # Scope-exit destruction under the keep policy.
        live = 0
    assert allocations == releases
    return dict(peak_buffers=peak, enabled=int(enabled), checks=checks,
                transfers=left+right, left_transfers=left, right_transfers=right,
                payload_allocations=allocations, payload_releases=releases)
