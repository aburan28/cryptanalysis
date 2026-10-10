"""Ten linear-source S3 blocks on the exact degree-41 Koblitz curve."""

N=41
WIDTH=5
BLOCKS=10

def nonzero_nonone(circuit,row):
    circuit.clauses.append(" ".join(map(str,row))+" 0")
    circuit.clauses.append(" ".join(map(str,row[1:]))+" 0")

def one_hot(circuit,row):
    circuit.clauses.append(" ".join(map(str,row))+" 0")
    for i in range(len(row)):
        for j in range(i+1,len(row)):
            circuit.clauses.append(f"-{row[i]} -{row[j]} 0")

def link(circuit,left,right,output):
    a=circuit.add(circuit.square(left),left)
    b=circuit.add(circuit.square(right),right)
    lhs=circuit.mul(circuit.mul(a,b),
                    circuit.add(circuit.square(output),output))
    rhs=circuit.square(circuit.add(circuit.add(left,right),output))
    circuit.require_zero(circuit.add(lhs,rhs))

def forbidden(code,row):
    return " ".join(str(-wire if code>>i&1 else wire)
                    for i,wire in enumerate(row))+" 0"

def build(circuit,bases_u,columns,target_us):
    if (len(bases_u)!=BLOCKS or len(target_us)!=4 or
            any(len(row)!=WIDTH for row in bases_u)):
        raise ValueError("ten W5 source bases and four target lifts required")
    masks=[[circuit.variable() for _ in range(WIDTH)] for _ in range(BLOCKS)]
    flags=[circuit.variable() for _ in range(4)]
    one_hot(circuit,flags)
    middle=[[circuit.variable() for _ in range(N)] for _ in range(8)]
    leaves=[circuit.linear_element(row,bases_u[i])
            for i,row in enumerate(masks)]
    for row in masks:
        for code in range(1<<WIDTH):
            if code not in columns:
                circuit.clauses.append(forbidden(code,row))
    aliases={}
    for mask,column in columns.items():
        aliases.setdefault(tuple(column),[]).append(mask)
    duplicate_clauses=0
    for i in range(BLOCKS):
        for j in range(i+1,BLOCKS):
            for group in aliases.values():
                for first in group:
                    for second in group:
                        circuit.clauses.append(forbidden(first,masks[i])[:-2]+" "+
                                               forbidden(second,masks[j]))
                        duplicate_clauses+=1
    for row in middle:
        nonzero_nonone(circuit,row)
    for i in range(5):
        link(circuit,leaves[2*i],leaves[2*i+1],middle[i])
    link(circuit,middle[0],middle[1],middle[5])
    link(circuit,middle[2],middle[3],middle[6])
    link(circuit,middle[5],middle[6],middle[7])
    target=circuit.linear_element(flags,target_us)
    link(circuit,middle[7],middle[4],target)
    return {"masks":masks,"flags":flags,"leaves":leaves,"middle":middle,
            "duplicate_column_clauses":duplicate_clauses,
            "primary_variables":BLOCKS*WIDTH+4+8*N}
