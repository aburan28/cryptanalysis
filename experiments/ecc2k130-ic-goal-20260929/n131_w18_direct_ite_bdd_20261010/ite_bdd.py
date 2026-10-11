"""Direct CNF encoding of the exact W18 source BDD."""


def emit_bdd_ite(cnf, root, nodes, selectors):
    """Assert the BDD root using one Tseitin variable per nontrivial decision."""
    literals = {0: cnf.false, 1: cnf.true}
    for node in sorted(nodes):
        bit, low, high = nodes[node]
        a, b, switch = literals[low], literals[high], selectors[bit]
        if a == cnf.false and b == cnf.true:
            out = switch
        elif a == cnf.true and b == cnf.false:
            out = -switch
        elif a == cnf.false:
            out = cnf.andLit(switch, b)
        elif b == cnf.false:
            out = cnf.andLit(-switch, a)
        elif a == cnf.true:
            out = cnf.orLit(-switch, b)
        elif b == cnf.true:
            out = cnf.orLit(switch, a)
        else:
            out = cnf.newVar()
            cnf.addClause([-switch, -out, b])
            cnf.addClause([-switch, out, -b])
            cnf.addClause([switch, -out, a])
            cnf.addClause([switch, out, -a])
        literals[node] = out
    cnf.addClause([literals[root]])
    return literals[root]


def check_decision_clauses():
    """Exhaustively check the four-clause nonconstant decision truth table."""
    for switch in (0, 1):
        for low in (0, 1):
            for high in (0, 1):
                for out in (0, 1):
                    clauses = ((not switch or not out or high),
                               (not switch or out or not high),
                               (switch or not out or low),
                               (switch or out or not low))
                    assert all(clauses) == (out == (high if switch else low))
