"""Exact ten-source S3 chain with sparse polynomial-W first-pair links."""

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

def forbidden(code,row):
    return " ".join(str(-wire if code>>i&1 else wire)
                    for i,wire in enumerate(row))+" 0"

def generic_link(circuit,left,right,output):
    a=circuit.add(circuit.square(left),left)
    b=circuit.add(circuit.square(right),right)
    lhs=circuit.mul(circuit.mul(a,b),
                    circuit.add(circuit.square(output),output))
    rhs=circuit.square(circuit.add(circuit.add(left,right),output))
    circuit.require_zero(circuit.add(lhs,rhs))

def low_product_link(circuit,mask_a,mask_b,basis_a,basis_b,u_a,u_b,output):
    # A(u)=u^2+u=w; w is linear in the low-degree source-mask basis.
    w_a=circuit.linear_element(mask_a,basis_a)
    w_b=circuit.linear_element(mask_b,basis_b)
    product=circuit.mul(w_a,w_b)
    lhs=circuit.mul(product,circuit.add(circuit.square(output),output))
    rhs=circuit.square(circuit.add(circuit.add(u_a,u_b),output))
    circuit.require_zero(circuit.add(lhs,rhs))

def frob(field,value,power):
    for _ in range(power):
        value=field.mul(value,value)
    return value

def build(circuit,bases_w,bases_u,columns,target_us,rotations=None,field=None):
    if (len(bases_w)!=BLOCKS or len(bases_u)!=BLOCKS or
            len(target_us)!=4 or
            any(len(row)!=WIDTH for row in bases_w+bases_u)):
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
    for row in middle:nonzero_nonone(circuit,row)
    for i in range(5):
        if rotations is None:
            low_product_link(circuit,masks[2*i],masks[2*i+1],
                             bases_w[2*i],bases_w[2*i+1],
                             leaves[2*i],leaves[2*i+1],middle[i])
        else:
            if field is None or len(rotations)!=BLOCKS:
                raise ValueError("pair-local frame requires field and ten rotations")
            inverse=(N-rotations[2*i])%N
            local_w=[[frob(field,value,inverse) for value in bases_w[j]]
                     for j in (2*i,2*i+1)]
            local_u=[[frob(field,value,inverse) for value in bases_u[j]]
                     for j in (2*i,2*i+1)]
            local_leaves=[circuit.linear_element(masks[2*i+j],local_u[j])
                          for j in range(2)]
            transform=[frob(field,1<<bit,inverse) for bit in range(N)]
            local_output=circuit.linear_element(middle[i],transform)
            low_product_link(circuit,masks[2*i],masks[2*i+1],
                             local_w[0],local_w[1],
                             local_leaves[0],local_leaves[1],local_output)
    generic_link(circuit,middle[0],middle[1],middle[5])
    generic_link(circuit,middle[2],middle[3],middle[6])
    generic_link(circuit,middle[5],middle[6],middle[7])
    target=circuit.linear_element(flags,target_us)
    generic_link(circuit,middle[7],middle[4],target)
    return {"masks":masks,"flags":flags,"leaves":leaves,"middle":middle,
            "duplicate_column_clauses":duplicate_clauses,
            "low_product_links":5,"generic_links":4,
            "pair_local_frobenius_frames":rotations is not None,
            "primary_variables":BLOCKS*WIDTH+4+8*N}
