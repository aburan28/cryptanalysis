"""Exact Boolean ideal/GB certificate without assignment enumeration.

Independent checker: no solver imports. Proof nodes establish output membership
in the input ideal; reverse inclusion and all relevant Buchberger pairs are
checked here. Polynomial arithmetic is in GF(2)[x]/(x_i^2+x_i), grevlex x0 first.
Work/retention exhaustion is inconclusive, never a verified/refuted result.
"""


class InvalidCertificate(Exception):
    pass


class VerificationBudget(Exception):
    pass


def verify(nvars, equations, basis, proof, *, max_work=2_000_000, max_retained_terms=500_000):
    stats = dict(work=0, retained_terms=0, proof_nodes=0, generator_checks=0,
                 basis_pairs=0, product_pairs_skipped=0, field_pairs=0, reduction_steps=0)

    def charge(work=1):
        stats['work'] += work
        if stats['work'] > max_work:
            raise VerificationBudget('operation budget')

    def integer(value, upper):
        if type(value) is not int or not 0 <= value < upper:
            raise InvalidCertificate('integer outside its declared range')
        return value

    def polynomial(terms, *, canonical=False):
        if not isinstance(terms, (list, tuple, set, frozenset)):
            raise InvalidCertificate('polynomial must be a finite term collection')
        charge(len(terms))
        result = set()
        for term in terms:
            integer(term, 1 << nvars)
            if term in result:
                if canonical:
                    raise InvalidCertificate('duplicate basis term')
                result.remove(term)
            else:
                result.add(term)
        return frozenset(result)

    def order(mask):
        return mask.bit_count(), -mask

    def leading(poly):
        charge(len(poly))
        return max(poly, key=order)

    def multiply(poly, mask):
        charge(len(poly))
        result = set()
        for term in poly:
            product = term | mask
            if product in result:
                result.remove(product)
            else:
                result.add(product)
        return frozenset(result)

    def add(left, right):
        charge(len(left)+len(right))
        return left ^ right

    def normal_form(poly, reducers):
        value, remainder = poly, set()
        while value:
            lm = leading(value)
            for reducer_lm, reducer in reducers:
                charge()
                if lm & reducer_lm == reducer_lm:
                    product = multiply(reducer, lm & ~reducer_lm)
                    # This property also guards ordering/arithmetic mistakes.
                    if not product or leading(product) != lm:
                        raise InvalidCertificate('nondecreasing reduction')
                    value = add(value, product)
                    stats['reduction_steps'] += 1
                    break
            else:
                remainder.add(lm)
                value = value - {lm}
        return frozenset(remainder)

    try:
        if type(nvars) is not int or not 1 <= nvars <= 4096:
            raise InvalidCertificate('variables must be in 1..4096')
        if type(max_work) is not int or type(max_retained_terms) is not int or min(max_work,max_retained_terms) < 0:
            raise InvalidCertificate('invalid verifier budget')
        if not isinstance(proof, dict) or proof.get('version') != 1 or proof.get('nvars') != nvars or proof.get('order') != 'grevlex-x0-first':
            raise InvalidCertificate('proof ring/version/order mismatch')
        if not isinstance(equations, (list,tuple)) or not isinstance(basis, (list,tuple)):
            raise InvalidCertificate('equations and basis must be finite sequences')
        charge(len(equations)+len(basis))
        inputs = [polynomial(row) for row in equations]
        output = [polynomial(row, canonical=True) for row in basis]
        if any(not row for row in output):
            raise InvalidCertificate('zero basis row')
        nodes, outputs = proof.get('nodes'), proof.get('outputs')
        if not isinstance(nodes, list) or not isinstance(outputs, list) or len(outputs) != len(output):
            raise InvalidCertificate('invalid proof graph/output shape')
        charge(len(nodes))
        values = []
        for node in nodes:
            if not isinstance(node, (tuple,list)) or not node:
                raise InvalidCertificate('malformed proof node')
            if node[0] == 'input' and len(node) == 2:
                value = inputs[integer(node[1],len(inputs))]
            elif node[0] == 'xor' and len(node) == 3:
                value = add(values[integer(node[1],len(values))],values[integer(node[2],len(values))])
            elif node[0] == 'mul' and len(node) == 3:
                value = multiply(values[integer(node[1],len(values))],integer(node[2],1 << nvars))
            else:
                raise InvalidCertificate('unsupported proof operation')
            stats['retained_terms'] += len(value)
            if stats['retained_terms'] > max_retained_terms:
                raise VerificationBudget('proof retention budget')
            values.append(value)
            stats['proof_nodes'] += 1
        for row, node in zip(output,outputs):
            if values[integer(node,len(values))] != row:
                raise InvalidCertificate('output is not its witnessed input combination')
        leads = [leading(row) for row in output]
        reducers = list(zip(leads,output))
        # Reverse inclusion: every original generator lies in the output ideal.
        for row in inputs:
            stats['generator_checks'] += 1
            if normal_form(row,reducers):
                raise InvalidCertificate('input generator has nonzero normal form')
        # Reducedness, in the squarefree quotient representation.
        for i, row in enumerate(output):
            for j, lm in enumerate(leads):
                if i == j:
                    continue
                charge(len(row))
                if any(term & lm == lm for term in row):
                    raise InvalidCertificate('basis is not reduced/minimal')
        # H={x_i^2+x_i}. H/H pairs reduce to zero. For g/H, coprime
        # leading terms use the product criterion. If x_i divides LM(g),
        # reduction of S(g,H_i) by H is precisely Boolean(x_i*g).
        for i, (lm,row) in enumerate(reducers):
            variables = lm
            while variables:
                bit = variables & -variables
                variables ^= bit
                stats['field_pairs'] += 1
                if normal_form(multiply(row,bit),reducers):
                    raise InvalidCertificate('implicit Boolean field pair has nonzero normal form')
            for other_lm, other in reducers[i+1:]:
                stats['basis_pairs'] += 1
                charge()
                # Ordinary-polynomial Buchberger product criterion: coprime
                # leading monomials have a zero S-remainder using this pair.
                # Adding the Boolean field generators preserves that proof.
                if not lm & other_lm:
                    stats['product_pairs_skipped'] += 1
                    continue
                common = lm | other_lm
                pair = add(multiply(row,common & ~lm),multiply(other,common & ~other_lm))
                if normal_form(pair,reducers):
                    raise InvalidCertificate('basis critical pair has nonzero normal form')
        return {'verified': True, 'status': 'verified', 'ideal_equality': True,
                'reduced_groebner_basis': True, 'method': 'derivation-DAG+Boolean-Buchberger',
                'root_count': None, 'solutions': None, 'stats': stats}
    except InvalidCertificate as error:
        return {'verified': False, 'status': 'rejected', 'reason': str(error), 'stats': stats}
    except VerificationBudget as error:
        return {'verified': False, 'status': 'inconclusive', 'reason': str(error), 'stats': stats}
