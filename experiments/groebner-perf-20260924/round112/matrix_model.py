"""Integer-row oracle with explicit early rewrite, fallback and charge prefixes."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'round108'))
from raw_model import model as raw_model, Limit
from early_model import rewrite, FIELDS

EARLY_FIELDS = ('mode', 'attempted', 'active_nodes', 'bound_checks',
                'bound_selected', 'bound_fallback', 'prune_visits')


def model(n, rows, degree, multiplier_degree, *, early_mode=1,
          parity_mode=1, parity_bytes=8388608, **limits):
    result = raw_model(n, rows, degree, multiplier_degree, minimal=True,
                       retain_raw=True, block=True, **limits)
    result['early'] = early = dict.fromkeys(EARLY_FIELDS, 0)
    early['mode'] = early_mode
    result['parity'] = dict.fromkeys(FIELDS, 0)
    result['parity']['mode'] = parity_mode
    stats = result['stats']
    maximum = limits.get('max_work', 20000000)
    if stats['status']:
        return result

    def pay(amount=1):
        if amount > maximum-stats['work']:
            raise Limit('matrix work budget')
        stats['work'] += amount

    def prune():
        original = result['proof']
        nodes, outputs = original['nodes'], original['outputs']
        needed = set(outputs)
        for i in reversed(range(len(nodes))):
            pay()
            early['prune_visits'] += 1
            if i not in needed:
                continue
            node = nodes[i]
            if node[0] != 'input': needed.add(node[1])
            if node[0] == 'xor': needed.add(node[2])
        remap, compact = {}, []
        for i, node in enumerate(nodes):
            pay()
            early['prune_visits'] += 1
            if i not in needed:
                continue
            remap[i] = len(compact)
            compact.append([node[0], remap[node[1]] if node[0] != 'input' else node[1]]+
                ([remap[node[2]]] if node[0] == 'xor' else [node[2]] if node[0] == 'mul' else []))
        result['proof'] = {**original, 'nodes': compact, 'outputs': [remap[i] for i in outputs]}

    def compress():
        rewritten = rewrite(result['proof'], len(rows), mode=parity_mode,
            max_bytes=parity_bytes, max_work=maximum-stats['work'], early_stats=early)
        result['parity'] = rewritten['stats']
        stats['work'] += rewritten['stats']['work']
        if rewritten['status']:
            raise Limit(rewritten['reason'])
        result['proof'] = rewritten['proof']

    try:
        if early_mode and parity_mode:
            early['attempted'] = 1
            compress()
            if not result['parity']['selected']:
                prune()
        else:
            prune()
            stats['output_nodes'] = len(result['proof']['nodes'])
            compress()
        stats['output_nodes'] = len(result['proof']['nodes'])
    except Limit as exc:
        result.update(basis=None, proof=None, reason=str(exc))
        stats['status'] = 2
    return result
