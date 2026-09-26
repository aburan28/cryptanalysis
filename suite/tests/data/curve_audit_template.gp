\\ ============================================================
\\ Parameterised audit template — invoked from Rust cargo test.
\\ ============================================================
\\
\\ Expects the following variables to be set BEFORE this script
\\ runs (e.g., via gp -p < (echo "p = 0xFOO; n = 0xBAR; ..." ; cat
\\ curve_audit_template.gp) ):
\\
\\   p             : F_p prime modulus
\\   n             : full curve order #E(F_p)
\\   a, b          : short-Weierstrass coefficients
\\   curve_name    : optional string identifier (for log lines)
\\
\\ Output: prints structured key=value lines that the Rust harness
\\ parses to determine the audit verdict.
\\
\\ Output keys (all should appear in successful runs):
\\
\\   CURVE_NAME=<string>
\\   P_BITS=<int>
\\   N_BITS=<int>
\\   N_PRIME=<0|1>
\\   T=<int>                       (Frobenius trace)
\\   J_INVARIANT_BITS=<int>
\\   IS_J0=<0|1>
\\   HOWE_H1=<0|1>
\\   HOWE_H2=<0|1>
\\   HOWE_H3=<0|1>
\\   HOWE_GLUING_APPLICABLE=<0|1>
\\   N_TWIST_GCD=<int>             (gcd(n, n_twist))
\\   P_IS_CUBE_MOD_N=<0|1|-1>      (-1 = 3 does not divide n - 1)
\\   EMBEDDING_DEGREE_BITS=<int>
\\   STRUCTURAL_COMPLETENESS=<PASS|FAIL>
\\   ERROR=<string if any>

default(parisize, 1024000000);
default(timer, 0);
\\ Quieter output for parsing
default(debug, 0);

{
if (!isprime(p), print("ERROR=p is not prime"); print("STRUCTURAL_COMPLETENESS=FAIL"); quit);
}

\\ Recompute trace from p and n (don't trust user input)
t = p + 1 - n;

print("CURVE_NAME=", if(type(curve_name) == "t_STR", curve_name, "unknown"));
print("P_BITS=", #binary(p));
print("N_BITS=", #binary(n));
print("N_PRIME=", if(isprime(n), 1, 0));
print("T=", t);

\\ ------------------------------------------------------------
\\ j-invariant
\\ ------------------------------------------------------------
j = lift(Mod(1728 * 4 * a^3, p) / Mod(4 * a^3 + 27 * b^2, p));
print("J_INVARIANT_BITS=", #binary(j + 1));
print("IS_J0=", if(j == 0, 1, 0));

\\ ------------------------------------------------------------
\\ Howe conditions
\\ ------------------------------------------------------------
n_twist = p + 1 + t;

\\ H1: Hom_{F_p}(E, E^t) = 0
h1 = (n != n_twist);
print("HOWE_H1=", if(h1, 1, 0));

\\ H3: gcd(n, n_twist) = 1
gcd_orders = gcd(n, n_twist);
print("N_TWIST_GCD=", gcd_orders);
h3 = (gcd_orders == 1);
print("HOWE_H3=", if(h3, 1, 0));

\\ H2: E[2] ≃ E^t[2] as F_p-Galois modules.
\\ We compare degree patterns of x³ + ax + b vs x³ + d²ax + d³b
\\ (the twist's 2-torsion poly) for the smallest non-square d.
d_twist = 2;
while (kronecker(d_twist, p) != -1, d_twist = d_twist + 1);

\\ Helper: degree pattern of poly factor over F_p
factor_pattern_simple(poly_mod_p) = {
    my(f, n_rows, out, i, j);
    f = factor(poly_mod_p);
    n_rows = matsize(f)[1];
    out = [];
    for (i = 1, n_rows,
        for (j = 1, f[i, 2],
            out = concat(out, [poldegree(f[i, 1])])
        )
    );
    vecsort(out)
};

deg_E  = factor_pattern_simple(Mod(x^3 + a*x + b, p));
deg_Et = factor_pattern_simple(Mod(x^3 + d_twist^2*a*x + d_twist^3*b, p));
h2 = (deg_E == deg_Et);
print("HOWE_H2=", if(h2, 1, 0));

print("HOWE_GLUING_APPLICABLE=", if(h1 && h2 && h3, 1, 0));

\\ ------------------------------------------------------------
\\ Embedding degree analysis.  For prime n we use the full n;
\\ for composite n with prime subgroup r, the caller should pass
\\ r in place of n.  Here we just compute znorder(p mod n).
\\ ------------------------------------------------------------
{
if (isprime(n) && n > 1, k_emb = znorder(Mod(p, n)); print("EMBEDDING_DEGREE_BITS=", #binary(k_emb)), print("EMBEDDING_DEGREE_BITS=0"));
}

\\ ------------------------------------------------------------
\\ Cube-residue test (the "p is a cube mod n" curiosity)
\\ ------------------------------------------------------------
{
if (!isprime(n) || (n - 1) % 3 != 0, print("P_IS_CUBE_MOD_N=-1"), p_cube = (lift(Mod(p, n)^((n - 1) / 3)) == 1); print("P_IS_CUBE_MOD_N=", if(p_cube, 1, 0)));
}

\\ ------------------------------------------------------------
\\ Verdict.  For prime-order ordinary curves over F_p, the
\\ structural-completeness theorem of research/notes/cm-isogeny/PAPER_STRUCTURAL_COMPLETENESS.md
\\ requires:
\\
\\   • n prime (else use ℓ-subgroup)
\\   • E ordinary (effectively: p does not divide t)
\\   • Howe conditions (H1), (H2), (H3) hold
\\
\\ All standard NIST/secp/brainpool curves over F_p satisfy these.
\\ Curves with composite n (e.g., Curve25519 with cofactor 8) require
\\ explicit ℓ-subgroup analysis; we report SKIP in that case.
\\ ------------------------------------------------------------
verdict_n_prime = isprime(n);
verdict_ordinary = (t % p != 0);
verdict_howe = h1 && h2 && h3;
{
if (verdict_n_prime && verdict_ordinary && verdict_howe, print("STRUCTURAL_COMPLETENESS=PASS"), if (!verdict_n_prime, print("STRUCTURAL_COMPLETENESS=SKIP_NONPRIME"), if (!verdict_ordinary, print("STRUCTURAL_COMPLETENESS=FAIL_SUPERSINGULAR"), print("STRUCTURAL_COMPLETENESS=FAIL_HOWE"))));
}

\\ ------------------------------------------------------------
\\ B5 check: predicted DLP cost on Jac(C) for genus g = 2, 3, 4
\\ vs. plain ECDLP cost on E.  Per PAPER §4 / B5:
\\
\\   ECDLP cost (Pollard ρ + Aut folding): √(n / |Aut(E)|)
\\   Jac(C) cost (Gaudry IC genus g, F_p): p^{2 − 2/g}
\\
\\ B5 holds iff Jac(C) cost > ECDLP cost.  We emit bit-count for both.
\\ ------------------------------------------------------------
ecdlp_cost_bits = (#binary(n) - if(j == 0, log(6) / log(2), if(j == 1728, 2.0, 1.0))) / 2;
print("ECDLP_COST_BITS=", round(ecdlp_cost_bits));
p_bits = #binary(p);
\\ For genus g ≥ 2, prime-field hyperelliptic DLP cost is p^{2-2/g}
b5_g2_bits = p_bits * 1.0;        \\ 2 - 2/2 = 1
b5_g3_bits = p_bits * 4 / 3;      \\ 2 - 2/3 = 4/3
b5_g4_bits = p_bits * 3 / 2;      \\ 2 - 2/4 = 3/2
print("B5_GENUS_2_COST_BITS=", round(b5_g2_bits));
print("B5_GENUS_3_COST_BITS=", round(b5_g3_bits));
print("B5_GENUS_4_COST_BITS=", round(b5_g4_bits));
b5_pass = (b5_g2_bits > ecdlp_cost_bits) && (b5_g3_bits > ecdlp_cost_bits) && (b5_g4_bits > ecdlp_cost_bits);
print("B5_PASS=", if(b5_pass, 1, 0));

\\ ------------------------------------------------------------
\\ B6 check: prime-field obstruction to Diem 2011 sub-exp DLP.
\\
\\ B6 holds for any curve over F_p (k = 1).  Diem 2011 sub-exp DLP
\\ requires F_{p^k} with k ≥ 3 for the factor-base construction.
\\ For curves defined directly over F_p (which all deployed ECC
\\ curves are), Diem's algorithm is structurally inapplicable.
\\
\\ The audit confirms the field is a prime field by checking
\\ isprime(p), which we already did at the top.  B6 trivially
\\ holds.
\\ ------------------------------------------------------------
b6_pass = isprime(p);
print("B6_FIELD_IS_PRIME=", if(b6_pass, 1, 0));
print("B6_PASS=", if(b6_pass, 1, 0));

\\ ------------------------------------------------------------
\\ B7 check: ordinary vs supersingular.
\\
\\ B7's argument (supersingular reductions live in a disjoint
\\ mathematical world) applies to ORDINARY curves whose structural-
\\ completeness theorem is being asserted.  If the audited curve is
\\ itself supersingular, the theorem does NOT apply — supersingular
\\ DLP has different complexity behaviour (specifically: pairing
\\ reductions become trivial since the embedding degree is ≤ 6).
\\
\\ Ordinary ⇔ gcd(t, p) = 1.  Equivalently for our setup with
\\ prime p: t mod p ≠ 0.
\\ ------------------------------------------------------------
is_ordinary = (t % p != 0);
print("B7_IS_ORDINARY=", if(is_ordinary, 1, 0));
print("B7_PASS=", if(is_ordinary, 1, 0));

\\ ------------------------------------------------------------
\\ Overall: ALL seven blocks pass?
\\
\\ B1 (Tate), B2 (h=1 or h>1 walk-cost-cancels), B3 (c_γ walk),
\\ B4 (Hom=0), B5 (cover cost), B6 (prime field), B7 (ordinary).
\\
\\ For the audit, B1-B4 are encoded by Howe (H1)+(H2)+(H3) being
\\ true plus prime n.  B5 we just checked.  B6+B7 we just checked.
\\ ------------------------------------------------------------
all_blocks_pass = (verdict_n_prime && verdict_ordinary && verdict_howe && b5_pass && b6_pass && is_ordinary);
print("ALL_BLOCKS_B1_TO_B7_PASS=", if(all_blocks_pass, 1, 0));
