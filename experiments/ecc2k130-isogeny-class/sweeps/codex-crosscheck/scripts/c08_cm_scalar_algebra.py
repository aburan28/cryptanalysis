# Algebraic re-derivation of Codex run-11 CM scalars (beta, gamma, delta, omega roots, norm-equation solutions)
# and of all 262 chart alignment scalars lambda_j, from scratch. Pure python3 (no Sage).
import json
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
cm = json.loads((W / "codex_inputs/curve-comparison/run-11-horizontal-core-fringe/cm-alignment.json").read_text())
N = 680564733841876926932320129493409985129
res = {"checks": []}
def chk(name, codex, ours):
    ok = str(codex) == str(ours)
    res["checks"].append({"name": name, "codex": str(codex), "ours": str(ours), "agree": ok})
    print("AGREE   " if ok else "DISAGREE", name, str(codex)[:60], "|", str(ours)[:60])
# 1. norm form x^2 + xy + 121046 y^2 = 11 * 2^16: all integer solutions by brute force
T = 11 * 2**16
sols = sorted([[x, y] for y in range(-3, 4) for x in range(-2000, 2001) if x*x + x*y + 121046*y*y == T])
# 2. roots of theta^2 - theta + 121046 mod N (theta = (1 + 263 sqrt(-7))/2 generates O_263)
#    via Tonelli-Shanks for sqrt(disc) with disc = 1 - 4*121046 = -484183
def sqrt_mod(a, p):
    a %= p
    assert pow(a, (p-1)//2, p) == 1
    qq, s = p-1, 0
    while qq % 2 == 0: qq //= 2; s += 1
    z = 2
    while pow(z, (p-1)//2, p) != p-1: z += 1
    m, c, t, r = s, pow(z, qq, p), pow(a, qq, p), pow(a, (qq+1)//2, p)
    while t != 1:
        i, t2 = 0, t
        while t2 != 1: t2 = t2*t2 % p; i += 1
        b = pow(c, 1 << (m-i-1), p); m, c, t, r = i, b*b % p, t*b*b % p, r*b % p
    return r
sq = sqrt_mod(-484183, N)
inv2 = pow(2, -1, N)
roots = sorted([(1 + sq) * inv2 % N, (1 - sq) * inv2 % N])
for o in cm["orbits"]:
    O = o["orbit"]
    chk(f"{O}: norm_equation_target", o["norm_equation_target"], T)
    chk(f"{O}: norm_equation_solutions (complete set)", sorted(o["norm_equation_solutions"]), sols)
    chk(f"{O}: omega_roots_mod_N", sorted(int(v) for v in o["omega_roots_mod_N"]), roots)
    th = int(o["unique_calibrated_match"]["omega_root"])
    x, y = o["unique_calibrated_match"]["x"], o["unique_calibrated_match"]["y"]
    delta = (x + y*th) % N
    chk(f"{O}: calibrated_delta = x + y*theta mod N", o["calibrated_delta_scalar_mod_N"], delta)
    beta = delta * pow(2**16, -1, N) % N
    chk(f"{O}: beta = delta / 2^16", o["beta_plus_scalar_mod_N"], beta)
    thc = (1 - th) % N                   # conjugate root
    deltabar = (x + y*thc) % N
    gamma = (-deltabar) % N              # Codex: minus-dual
    chk(f"{O}: gamma = -conj(delta)", o["gamma_minus_scalar_mod_N"], gamma)
    chk(f"{O}: beta*gamma = -11", o["beta_times_gamma_mod_N"], beta*gamma % N)
    chk(f"{O}: delta*conj(delta) = 11*2^16 mod N", T, delta*deltabar % N)
    # chart scalars: path from chart k to shift 0: k + 16*dir*steps == 0 mod 131; lambda = beta^s (dir +1) or gamma^s (dir -1)
    bad_shift = bad_lam = 0
    for c in o["charts"]:
        k = int(c["curve_id"][1:]); s = c["path_steps"]; d = c["path_direction"]
        if (k + 16*d*s) % 131 != 0: bad_shift += 1
        lam = pow(beta if d == 1 else gamma, s, N)
        if str(lam) != c["alignment_scalar_mod_N"]: bad_lam += 1
        if not (c["P_alignment_verified"] and c["Q_alignment_verified"]): bad_lam += 1000
    chk(f"{O}: 131 charts, path shift consistency failures", 0, bad_shift)
    chk(f"{O}: 131 charts, lambda_j == beta^s / gamma^s failures", 0, bad_lam)
    # shortest-path claim: steps = min over direction of |16^{-1} * (-k)| mod 131
    inv16 = pow(16, -1, 131)
    steps = []
    for c in o["charts"]:
        k = int(c["curve_id"][1:]); sp = (-k * inv16) % 131; sm = (k * inv16) % 131
        steps.append(min(sp, sm))
        if min(sp, sm) != c["path_steps"]: bad_shift += 1
    chk(f"{O}: path_steps are shortest", 0, bad_shift)
    res[f"{O}_mean_path_len_all131"] = sum(steps)/131
    res[f"{O}_mean_path_len_130_nonref"] = sum(steps)/130
    res[f"{O}_max_path_len"] = max(steps)
print({k: v for k, v in res.items() if k != "checks"})
(W / "raw" / "c08_cm_scalar_algebra.json").write_text(json.dumps(res, indent=1))
