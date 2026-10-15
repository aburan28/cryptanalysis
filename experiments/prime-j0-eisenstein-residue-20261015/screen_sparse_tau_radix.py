#!/usr/bin/env python3
"""Exact integer screen for the sparse Eisenstein radix 127 + 128*tau."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent
FIXTURE_ARCHIVE = HERE/'horner-native-provenance.tar.gz'
FIXTURE_MEMBER = ('prime-j0-alt-radix-horner-terminal-g/'
                  'src/bin/mixed640_uniform_fixture.json')
ORDER = int('fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141',16)
LAMBDA_TAU = int('ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0',16)
W = (671331852483699643819086596696745227419,
     -367917413016453100223835821029139468248)
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
RADIX = (127,128)
NORM = 114049
TAU_RESIDUE = -892
STEPS = 15


def norm(pair):
    a,b = pair
    return a*a+3*a*b+3*b*b


def multiply(pair):
    a,b = pair
    return 127*a-384*b,128*a+511*b


def omega(pair):
    a,b = pair
    return a+3*b,-a-2*b


def canonical(pair):
    values = []
    for _ in range(3):
        values.extend((pair,(-pair[0],-pair[1])))
        pair = omega(pair)
    return min(values)


def nearest_digit(residue):
    if residue == 0:
        return (0,0)
    best = None
    coefficient = TAU_RESIDUE**2-3*TAU_RESIDUE+3
    for lift_number in range(-2,3):
        lift = residue+lift_number*NORM
        center = -((3-2*TAU_RESIDUE)*lift)//(2*coefficient)
        for b in range(center-2,center+3):
            a = lift-TAU_RESIDUE*b
            score = (norm((a,b)),abs(b),abs(a),a,b)
            if best is None or score < best:
                best = score
    return best[3],best[4]


def digit_table():
    result = [nearest_digit(residue) for residue in range((NORM+1)//2)]
    assert all((a+TAU_RESIDUE*b-residue)%NORM == 0
               for residue,(a,b) in enumerate(result))
    return result


def choose_pair(scalar):
    # Four exact corners of the fixed scalar lattice, with determinant ORDER.
    x = scalar*V[1]//ORDER
    y = -scalar*W[1]//ORDER
    candidates = [(scalar-m*W[0]-n*V[0], -m*W[1]-n*V[1])
                  for m in (x,x+1) for n in (y,y+1)]
    return min(candidates,key=lambda pair:(norm(pair),abs(pair[1]),abs(pair[0]),pair))


def step(pair,table):
    a,b = pair
    residue = (a+TAU_RESIDUE*b)%NORM
    negative = residue > (NORM-1)//2
    index = NORM-residue if negative else residue
    da,db = table[index]
    if negative:
        da,db = -da,-db
    ra,rb = a-da,b-db
    qa,qb = 511*ra+384*rb,-128*ra+127*rb
    assert qa%NORM == qb%NORM == 0
    quotient = qa//NORM,qb//NORM
    assert tuple(x+y for x,y in zip((da,db),multiply(quotient))) == pair
    return (da,db),quotient


def main():
    assert norm(RADIX) == NORM
    assert 127-892*128 == -NORM
    assert W[0]*V[1]-W[1]*V[0] == ORDER
    assert all((a+b*LAMBDA_TAU)%ORDER == 0 for a,b in (W,V))
    table = digit_table()
    digit_seeds = sorted({canonical(pair) for pair in table})
    digit_max_norm = max(map(norm,table))
    # The selector has |a|,|b| < 2^130. The weighted norm inequality in
    # AlternateRadix bounds each exact quotient using the exhaustive digit cap.
    analytic_terminal_bound = 7*(2**130)**2
    for _ in range(STEPS):
        analytic_terminal_bound = (
            101*analytic_terminal_bound+10100*digit_max_norm)//(100*NORM)
    assert analytic_terminal_bound < 5000
    terminal_cap = analytic_terminal_bound+1
    terminal_table = [(a,b) for a in range(-100,101) for b in range(-100,101)
                      if norm((a,b)) < terminal_cap]
    terminal_seeds = sorted({canonical(pair) for pair in terminal_table})
    with tarfile.open(FIXTURE_ARCHIVE,'r:gz') as archive:
        fixture = archive.extractfile(FIXTURE_MEMBER).read()
    panel = json.loads(fixture)
    max_terminal_norm = 0
    max_terminal_coordinate = 0
    terminal_points = set()
    for case in panel['cases']:
        scalar = int(case['scalar_hex'],16)%ORDER
        original = choose_pair(scalar)
        assert (original[0]+original[1]*LAMBDA_TAU)%ORDER == scalar
        pair = original
        digits = []
        for _ in range(STEPS):
            digit,pair = step(pair,table)
            digits.append(digit)
        reconstructed = pair
        for digit in reversed(digits):
            value = multiply(reconstructed)
            reconstructed = value[0]+digit[0],value[1]+digit[1]
        assert reconstructed == original
        terminal_points.add(pair)
        max_terminal_norm = max(max_terminal_norm,norm(pair))
        max_terminal_coordinate = max(max_terminal_coordinate,abs(pair[0]),abs(pair[1]))
    result = {
        'schema':1,'radix_pair':RADIX,'radix_norm':NORM,
        'tau_residue':TAU_RESIDUE,'steps':STEPS,
        'fixture_sha256':sha256(fixture).hexdigest(),
        'checked_distinct_scalars':len(panel['cases']),
        'digit_residue_count':len(table),
        'digit_max_norm':digit_max_norm,
        'digit_table_sha256':sha256(json.dumps(table,separators=(',',':')).encode()).hexdigest(),
        'digit_seed_count_including_zero':len(digit_seeds),
        'digit_seed_sha256':sha256(json.dumps(digit_seeds,separators=(',',':')).encode()).hexdigest(),
        'conditional_terminal_norm_limit_exclusive':terminal_cap,
        'conditional_terminal_seed_count_including_zero':len(terminal_seeds),
        'terminal_max_norm':max_terminal_norm,
        'terminal_max_absolute_coordinate':max_terminal_coordinate,
        'distinct_terminal_pairs':len(terminal_points),
        'terminal_pairs_sha256':sha256(json.dumps(sorted(terminal_points),separators=(',',':')).encode()).hexdigest(),
        'point_replay_status':'open_native_group_check',
    }
    output = HERE/'sparse-tau-radix-screen.json'
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
