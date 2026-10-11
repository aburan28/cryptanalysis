"""Positive-polarity CNF encoding of the exact W18 source BDD."""


def emit_positive_bdd(cnf, root, nodes, selectors):
    """Assert a BDD root with implications toward selected children only."""
    literals = {0: cnf.false, 1: cnf.true}
    for node in sorted(nodes):
        bit, low, high = nodes[node]
        a, b, switch = literals[low], literals[high], selectors[bit]
        if a == cnf.false and b == cnf.true:
            out = switch
        elif a == cnf.true and b == cnf.false:
            out = -switch
        else:
            out = cnf.newVar()
            if a != cnf.true:
                cnf.addClause([-out, switch] + ([] if a == cnf.false else [a]))
            if b != cnf.true:
                cnf.addClause([-out, -switch] + ([] if b == cnf.false else [b]))
        literals[node] = out
    cnf.addClause([literals[root]])
    return literals[root]


def check_positive_gate():
    """Check the local implication truth table for every binary assignment."""
    for switch in (0, 1):
        for low in (0, 1):
            for high in (0, 1):
                for out in (0, 1):
                    clauses = ((not out or switch or low),
                               (not out or not switch or high))
                    assert all(clauses) == (not out or (high if switch else low))
