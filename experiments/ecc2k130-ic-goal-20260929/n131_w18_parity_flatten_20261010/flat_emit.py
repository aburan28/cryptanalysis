"""Emit unshared linear IR subgraphs as one native XOR constraint."""


def _lit_expr(lit, cnf):
    if lit == cnf.true:
        return frozenset(), True
    if lit == cnf.false:
        return frozenset(), False
    return frozenset((abs(lit),)), lit < 0


def _xor(a, b):
    return a[0] ^ b[0], a[1] ^ b[1]


def _literal(expr, cnf, counters):
    terms, parity = expr
    if not terms:
        return cnf.true if parity else cnf.false
    if len(terms) == 1:
        value = next(iter(terms))
        return -value if parity else value
    value = cnf.newVar()
    cnf.addXor(sorted(terms) + [value], parity)
    counters["materialized_parities"] += 1
    counters["materialized_terms"] += len(terms)
    counters["maximum_parity_terms"] = max(counters["maximum_parity_terms"],
                                             len(terms))
    return value


def _assert_zero(expr, cnf, counters):
    terms, parity = expr
    if not terms:
        if parity:
            raise ValueError("constant-one root")
        return
    if len(terms) == 1:
        cnf.assertZero(_literal(expr, cnf, counters))
        return
    cnf.addXor(sorted(terms), parity)
    counters["direct_root_parities"] += 1
    counters["maximum_parity_terms"] = max(counters["maximum_parity_terms"],
                                             len(terms))


def emit_constraints(prog, roots, deltas, inputs, cnf):
    """Encode the same Boolean DAG and assert roots=0, each delta!=0.

    Only XOR nodes with one live consumer are inlined. Shared XOR nodes and
    every nonlinear operand are materialized, preserving DAG semantics.
    """
    all_roots = list(roots) + [bit for delta in deltas for bit in delta]
    uses = prog.refCounts(all_roots)
    remaining = list(uses)
    expressions = {}
    counters = {"materialized_parities": 0, "materialized_terms": 0,
                "maximum_parity_terms": 0, "direct_root_parities": 0,
                "unshared_xors_inlined": 0}
    for index, ref in enumerate(prog.inputRef):
        if ref is not None and uses[index]:
            expressions[index] = _lit_expr(inputs[ref], cnf)

    def take(index):
        result = expressions[index]
        remaining[index] -= 1
        if remaining[index] == 0:
            del expressions[index]
        return result

    for index, node in enumerate(prog.ops):
        if node is None or not uses[index]:
            continue
        op, args = node
        if op == "xor":
            result = _xor(take(args[0]), take(args[1]))
            if uses[index] > 1:
                result = _lit_expr(_literal(result, cnf, counters), cnf)
            else:
                counters["unshared_xors_inlined"] += 1
        elif op == "and":
            a = _literal(take(args[0]), cnf, counters)
            b = _literal(take(args[1]), cnf, counters)
            result = _lit_expr(cnf.andLit(a, b), cnf)
        else:
            raise ValueError("unsupported IR operation: " + op)
        expressions[index] = result

    for root in roots:
        _assert_zero((frozenset(), False) if root is None else take(root),
                     cnf, counters)
    for delta in deltas:
        cnf.addClause([_literal((frozenset(), False) if bit is None else
                                take(bit), cnf, counters) for bit in delta])
    assert not expressions
    return counters
