"""Native-free output-parity graph transform and declared charge model."""
FIELDS = ('mode', 'selected', 'fallback_outputs', 'fallback_bytes', 'fallback_size',
          'fallback_shape', 'input_nodes', 'outputs', 'peak_metadata_bytes',
          'visited_nodes', 'parity_edges', 'leaves', 'incidences', 'emitted_nodes', 'work')


class WorkLimit(Exception):
    pass


class TooLarge(Exception):
    pass


def rewrite(proof, equations, *, mode=1, max_bytes=8388608, max_work=20000000):
    stats = dict.fromkeys(FIELDS, 0)
    stats.update(mode=mode, input_nodes=len(proof['nodes']), outputs=len(proof['outputs']))
    result = dict(proof=proof, stats=stats, status=0, reason=None)

    def pay(amount=1):
        if amount > max_work-stats['work']:
            raise WorkLimit()
        stats['work'] += amount

    if not mode:
        return result
    try:
        nodes, outputs = proof['nodes'], proof['outputs']
        pay()
        if not outputs or len(outputs) > 64:
            stats['fallback_outputs'] = 1
            return result
        size = 8*len(nodes)+4*(equations+len(outputs))
        if size > max_bytes:
            stats['fallback_bytes'] = 1
            return result
        pay(len(nodes)+equations+len(outputs))
        owners = [0]*len(nodes)
        roots, inputs = [None]*len(outputs), [None]*equations
        stats['peak_metadata_bytes'] = size
        for i, output in enumerate(outputs):
            pay()
            if output >= len(nodes):
                stats['fallback_shape'] = 1
                return result
            owners[output] ^= 1 << i
        graph = []

        def emit(node):
            pay()
            if not nodes or len(graph) >= len(nodes)-1:
                raise TooLarge()
            graph.append(node)
            stats['emitted_nodes'] = len(graph)
            return len(graph)-1

        def original(equation):
            pay()
            if inputs[equation] is None:
                inputs[equation] = emit(['input', equation])
            return inputs[equation]

        for i in reversed(range(len(nodes))):
            pay()
            stats['visited_nodes'] += 1
            mask = owners[i]
            if not mask:
                continue
            node = nodes[i]
            if node[0] == 'xor':
                if node[1] >= i or node[2] >= i:
                    stats['fallback_shape'] = 1
                    return result
                pay(2)
                owners[node[1]] ^= mask
                owners[node[2]] ^= mask
                stats['parity_edges'] += 2
                continue
            if node[0] == 'input' and node[1] < equations:
                value = original(node[1])
            elif node[0] == 'mul' and node[1] < i:
                pay()
                source = nodes[node[1]]
                if source[0] != 'input' or source[1] >= equations:
                    stats['fallback_shape'] = 1
                    return result
                value = emit(['mul', original(source[1]), node[2]])
            else:
                stats['fallback_shape'] = 1
                return result
            stats['leaves'] += 1
            while mask:
                pay()
                bit = mask & -mask
                j = bit.bit_length()-1
                mask ^= bit
                stats['incidences'] += 1
                roots[j] = value if roots[j] is None else emit(['xor', roots[j], value])
        for root in roots:
            pay()
            if root is None:
                stats['fallback_shape'] = 1
                return result
        result['proof'] = {**proof, 'nodes': graph, 'outputs': roots}
        stats['selected'] = 1
    except TooLarge:
        stats['fallback_size'] = 1
    except WorkLimit:
        result.update(proof=None, status=2, reason='matrix work budget')
    return result
