# Red team 2, script 4: cost model for the MITM/Kani representation of the ascending p-isogeny.
# Explicit assumptions (NOT measured -- no char-2 higher-dimensional isogeny code exists here):
#   node cost at tree depth d = (1 + npush_d) * C * l_d^g  operations in F_{q^kd},
#   an F_{q^k} multiplication = k^1.585 F_q multiplications (Karatsuba),
#   C in [C_lo, C_hi] (theta level-3 / canonical-lift overheads), g = 2 or 4 (dimension of the product).
#   Guess tree: branching (l_i - 1) at each A-prime (the +-1 ambiguity halves the total), smallest l last;
#   c = 3^n part: 4*3^(ceil(n/2)-1) guesses at the root.  Both halves F1 and F2bar are walked.
import json, math
elk = {l: (k, kx) for l, k, kx in json.load(open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2_elkies.json'))['elkies_first_40']}
def model(primes, c, g, C):
    ls = sorted(primes, reverse=True)           # largest first, smallest last
    n3 = 0; cc = c
    while cc > 1: cc //= 3; n3 += 1
    root = 4 * 3 ** ((n3 + 1) // 2 - 1) if c > 1 else 1
    total = 0.0; nodes = root / 2
    for d, l in enumerate(ls):
        nodes *= (l - 1)
        k = elk[l][0]
        npush = 2 * (len(ls) - d - 1)            # two eigen-points per later prime pushed through this step
        total += nodes * (1 + npush) * C * l ** g * k ** 1.585
    return 2 * total                              # F1 and F2bar
rho_M = 2 ** 63.394                               # E0 rho: 2^60.809 iterations x ~6 M (rt3_misc.json)
cases = {
  'dim2_c81_A=29.71.137.179': ([29, 71, 137, 179], 81, 2),
  'dim2_c3_A=11.23.79.107.109': ([11, 23, 79, 107, 109], 3, 2),
  'dim4_c1_A=23.37.53.67.137 (Galbraith two-squares)': ([23, 37, 53, 67, 137], 1, 4),
}
out = {}
for name, (pr, c, g) in cases.items():
    row = {}
    for C in (9, 100, 1000):
        cost = model(pr, c, g, C)
        row['C=%d' % C] = dict(log2_Fq_mults=round(math.log2(cost), 2),
                               effective_log2_M_E0_rho_plus_transport=round(math.log2(rho_M + cost), 3))
    out[name] = row
out['E0_rho_log2_M'] = round(math.log2(rho_M), 3)
out['floor_native_rho_log2_M'] = round(math.log2(2 ** 64.326 * 6), 3)
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt4_transport_cost.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
