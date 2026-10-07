"""Bounded proof substitution for F4 seeded by witnessed original-input rows.

This is an untimed Python reference for a prospective native continuation.
The result still needs independent verification against the original inputs.
"""


class Stop(Exception):
    pass


def compose(seed, continuation, originals, *, max_work, max_nodes):
    stats = dict(work=0, seed_nodes=0, continuation_nodes=0,
                 combined_nodes=0, retained_nodes=0, retained_outputs=0)
    result = dict(status='inconclusive', proof=None, stats=stats)

    def pay(amount=1):
        if amount > max_work-stats['work']:
            raise Stop('composition work budget')
        stats['work'] += amount

    def integer(value, bound):
        if type(value) is not int or not 0 <= value < bound:
            raise ValueError('proof integer outside its declared range')
        return value

    try:
        integer(max_work, 1 << 64)
        integer(max_nodes, 10000001)
        integer(originals, 4097)
        n = integer(seed['nvars'], 65)
        if not n:
            raise ValueError('empty ring')
        for proof in (seed, continuation):
            if (proof['version'], proof['nvars'], proof['order']) != (1, n, 'grevlex-x0-first'):
                raise ValueError('proof ring/version/order mismatch')
            if not isinstance(proof['nodes'], list) or not isinstance(proof['outputs'], list):
                raise ValueError('invalid graph containers')
        graph = []

        def emit(node):
            if len(graph) >= max_nodes:
                raise Stop('composition node budget')
            pay()
            graph.append(node)
            stats['combined_nodes'] = len(graph)
            return len(graph)-1

        def validate(node, prior, inputs):
            pay()
            if not isinstance(node, list) or not node:
                raise ValueError('invalid proof node')
            op = node[0]
            if op == 'input' and len(node) == 2:
                integer(node[1], inputs)
            elif op in ('mul', 'xor') and len(node) == 3:
                integer(node[1], prior)
                integer(node[2], (1 << n) if op == 'mul' else prior)
            else:
                raise ValueError('unsupported proof operation')

        for i, node in enumerate(seed['nodes']):
            validate(node, i, originals)
            emit(list(node))
            stats['seed_nodes'] += 1
        pay(len(seed['outputs']))
        inputs = [integer(i, len(graph)) for i in seed['outputs']]
        for e in range(originals):
            inputs.append(emit(['input', e]))
        mapping = []
        for i, node in enumerate(continuation['nodes']):
            validate(node, i, len(inputs))
            if node[0] == 'input':
                pay()
                mapped = inputs[node[1]]
            else:
                mapped = emit([node[0], mapping[node[1]],
                    node[2] if node[0] == 'mul' else mapping[node[2]]])
            mapping.append(mapped)
            stats['continuation_nodes'] += 1
        pay(len(continuation['outputs']))
        outputs = [mapping[integer(i, len(mapping))] for i in continuation['outputs']]
        pay(len(graph))
        needed = bytearray(len(graph))
        for i in outputs:
            pay()
            needed[i] = 1
        for i in reversed(range(len(graph))):
            pay()
            if needed[i]:
                node = graph[i]
                for child in node[1:2] if node[0] == 'mul' else node[1:3] if node[0] == 'xor' else []:
                    pay()
                    needed[child] = 1
        pay(len(graph))
        remap = [None]*len(graph)
        compact = []
        for i, node in enumerate(graph):
            pay()
            if needed[i]:
                pay()
                remap[i] = len(compact)
                compact.append([node[0], node[1] if node[0] == 'input' else remap[node[1]]]+
                    ([remap[node[2]]] if node[0] == 'xor' else [node[2]] if node[0] == 'mul' else []))
                stats['retained_nodes'] += 1
        pay(len(outputs))
        result['proof'] = dict(version=1, nvars=n, order='grevlex-x0-first',
                               nodes=compact, outputs=[remap[i] for i in outputs])
        stats['retained_outputs'] = len(outputs)
        result['status'] = 'composed-unverified'
    except Stop as error:
        result['reason'] = str(error)
    except (ValueError, KeyError, TypeError) as error:
        result.update(status='invalid', reason=str(error))
    return result
