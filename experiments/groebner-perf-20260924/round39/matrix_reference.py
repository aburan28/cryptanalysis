"""Untimed exact matrix pilot over small Boolean-function rings; not a solver."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random


def combination(values, target):
    pivots = {}
    for i, value in enumerate(values):
        provenance = 1 << i
        while value:
            bit = value.bit_length()-1
            if bit not in pivots:
                pivots[bit] = value, provenance
                break
            old, source = pivots[bit]
            value ^= old
            provenance ^= source
    answer = 0
    while target:
        bit = target.bit_length()-1
        if bit not in pivots:
            return None
        value, source = pivots[bit]
        target ^= value
        answer ^= source
    return answer


def shared_elimination(original, lanes):
    """Use only constant row combinations yielding an all-one unit pivot."""
    unit = (1 << lanes)-1
    rows = [list(row) for row in original]
    m, n = len(rows), len(rows[0])
    assert all(len(row)==n and all(0 <= value <= unit for value in row) for row in rows)
    proof = [[unit if i==j else 0 for j in range(m)] for i in range(m)]
    rank, pivots = 0, []
    for column in range(n-1,-1,-1):
        selected = combination([rows[i][column] for i in range(rank,m)],unit)
        if selected is None:
            continue
        indices = [rank+i for i in range(m-rank) if selected >> i & 1]
        assert indices
        replacement = indices[0]
        new_row, new_proof = [0]*n, [0]*m
        for i in indices:
            for j in range(n):
                new_row[j] ^= rows[i][j]
            for j in range(m):
                new_proof[j] ^= proof[i][j]
        # The replacement occurs with coefficient one in the combination,
        # making this a reversible row operation at every specialization.
        assert new_row[column] == unit
        rows[replacement], proof[replacement] = new_row, new_proof
        rows[rank], rows[replacement] = rows[replacement], rows[rank]
        proof[rank], proof[replacement] = proof[replacement], proof[rank]
        for i in range(m):
            if i == rank:
                continue
            multiplier = rows[i][column]
            for j in range(n):
                rows[i][j] ^= multiplier & rows[rank][j]
            for j in range(m):
                proof[i][j] ^= multiplier & proof[rank][j]
        pivots.append(column)
        rank += 1
        if rank == m:
            break
    return rows, proof, pivots


def identity_valid(original, rows, proof):
    for i,row in enumerate(rows):
        for j,value in enumerate(row):
            reconstructed = 0
            for k,source in enumerate(original):
                reconstructed ^= proof[i][k] & source[j]
            if reconstructed != value:
                return False
    return True


def lane_span(matrix, lane):
    # Independent exhaustive GF(2) span, not a second execution of the pilot.
    rows = [sum(((value >> lane) & 1) << j for j,value in enumerate(row)) for row in matrix]
    span = {0}
    for row in rows:
        span |= {value ^ row for value in tuple(span)}
    return span


def check(original, lanes):
    rows, proof, pivots = shared_elimination(original,lanes)
    assert identity_valid(original,rows,proof)
    ranks = []
    for lane in range(lanes):
        expected = lane_span(original,lane)
        assert lane_span(rows,lane) == expected
        ranks.append(len(expected).bit_length()-1)
    assert len(pivots) <= min(ranks)
    return len(pivots), min(ranks), max(ranks), rows, proof


def main(output):
    if output.exists():
        raise FileExistsError(output)
    cases, missed, ranks = Counter(), Counter(), Counter()
    for bits in (1,2):
        lanes = 1 << bits
        for entries in itertools.product(range(1 << lanes),repeat=4):
            result = check([entries[:2],entries[2:]],lanes)
            key = str(bits)
            cases[key] += 1
            missed[key] += result[0] < result[1]
            ranks[str((bits,*result[:3]))] += 1
    rng = random.Random(2026092939)
    random_cases = 0
    for bits in (1,2,3,4):
        lanes = 1 << bits
        for _ in range(256):
            m,n = rng.randrange(1,7),rng.randrange(1,9)
            check([[rng.getrandbits(lanes) for _ in range(n)] for _ in range(m)],lanes)
            random_cases += 1
    # Every lane has a nonzero entry, but no constant combination is the
    # all-one function. This intentionally limited pilot must not divide by
    # either partial coefficient or claim complete elimination.
    counterexample = [[0b1110],[0b1101]]
    result = check(counterexample,4)
    assert result[:3] == (0,1,1)
    assert check([[0b01]],2)[:3] == (0,0,1)
    original = [[15,0],[0,15]]
    rows, proof, _ = shared_elimination(original,4)
    proof[0][0] ^= 1
    assert not identity_valid(original,rows,proof)
    rows, proof, _ = shared_elimination(original,4)
    rows[0][0] ^= 1
    assert not identity_valid(original,rows,proof)
    report = {'schema':'block-symbolic-matrix-pilot/1','status':'PASS',
              'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope':'Exact matrix/provenance correctness only. No polynomial solver, performance, novelty or asymptotic claim.',
              'exhaustive_two_by_two_cases_by_symbolic_bits':dict(cases),
              'random_cases':random_cases,'random_seed':2026092939,
              'missed_uniform_rank_by_symbolic_bits':dict(missed),
              'rank_histogram':dict(ranks),'corruption_controls_rejected':2,
              'counterexample':{'rows':counterexample,'lanes':4,'shared_pivots':0,'minimum_lane_rank':1},
              'rank_changing_control':{'rows':[[1]],'lanes':2,'minimum_rank':0,'maximum_rank':1}}
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rank_histogram'},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
