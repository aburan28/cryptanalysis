"""Exact W19 seven-source XCNF with rational masks and folded-column guards."""

N = 131
WIDTH = 19
BLOCKS = 7


def nonzero_nonone(circuit, row):
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    circuit.clauses.append(" ".join(map(str, row[1:])) + " 0")


def one_hot(circuit, row):
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    for i in range(len(row)):
        for j in range(i+1,len(row)):
            circuit.clauses.append(f"-{row[i]} -{row[j]} 0")


def link(circuit, left, right, output):
    a = circuit.add(circuit.square(left),left)
    b = circuit.add(circuit.square(right),right)
    lhs = circuit.mul(circuit.mul(a,b),
                      circuit.add(circuit.square(output),output))
    rhs = circuit.square(circuit.add(circuit.add(left,right),output))
    circuit.require_zero(circuit.add(lhs,rhs))


def forbidden_clause(mask,wires):
    return " ".join(str(-wire if mask>>bit&1 else wire)
                    for bit,wire in enumerate(wires))+" 0"


def build(circuit,bases_u,valid_masks,alias_pairs,target_us):
    if (len(bases_u)!=BLOCKS or any(len(row)!=WIDTH for row in bases_u) or
            len(target_us)!=4):
        raise ValueError("wrong W19 seven-source formula inputs")
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(BLOCKS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit,flags)
    middle = [[circuit.variable() for _ in range(N)] for _ in range(5)]
    leaves = [circuit.linear_element(row,bases_u[i]) for i,row in enumerate(masks)]
    invalid = 0
    for code in range(1<<WIDTH):
        if code in valid_masks:
            continue
        for row in masks:
            circuit.clauses.append(forbidden_clause(code,row))
        invalid += 1
    same_mask_clauses = alias_clauses = 0
    for i in range(BLOCKS):
        for j in range(i+1,BLOCKS):
            differences = [circuit.xor((a,b))
                           for a,b in zip(masks[i],masks[j])]
            circuit.clauses.append(" ".join(map(str,differences))+" 0")
            same_mask_clauses += 1
            for first,second in alias_pairs:
                circuit.clauses.append(
                    forbidden_clause(first,masks[i])[:-2]+" "+
                    forbidden_clause(second,masks[j]))
                circuit.clauses.append(
                    forbidden_clause(second,masks[i])[:-2]+" "+
                    forbidden_clause(first,masks[j]))
                alias_clauses += 2
    for row in middle:
        nonzero_nonone(circuit,row)
    link(circuit,leaves[0],leaves[1],middle[0])
    link(circuit,leaves[2],leaves[3],middle[1])
    link(circuit,leaves[4],leaves[5],middle[2])
    link(circuit,middle[0],middle[1],middle[3])
    link(circuit,middle[3],middle[2],middle[4])
    target = circuit.linear_element(flags,target_us)
    link(circuit,middle[4],leaves[6],target)
    return {"masks":masks,"flags":flags,"leaves":leaves,"middle":middle,
            "invalid_mask_count":invalid,
            "invalid_mask_clauses":invalid*BLOCKS,
            "same_mask_clauses":same_mask_clauses,
            "alias_clauses":alias_clauses,
            "primary_variables":BLOCKS*WIDTH+4+5*N}
