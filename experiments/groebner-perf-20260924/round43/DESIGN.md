# Exact partial-affine residual certificate

This is an isolated native implementation of the independently validated
Python mathematical prototype. It remains outside the accepted query path;
the package supplies optimized/UBSan validation and an independent audit.

For original Boolean residual equations F_0,...,F_(e-1), a certificate consists
only of coefficient vectors u_j in F_2^e. The checker reconstructs
g_j = sum_i u_(j,i) F_i from its own original packed input, rejects any g_j
with a nonlinear coefficient, and independently reduces the affine system.
It never accepts the producer's pivots, rank, consistency flag or roots.

If the independently checked system is inconsistent, the original system
has no roots. Otherwise, if its rank is r in y variables, the checker visits
every one of its 2^(y-r) assignments and evaluates the original equations.
Every original root satisfies each verified consequence, so this process
loses no original root and accepts no false root. Dependent or zero witness
rows cannot inflate rank. Sorting visits only discovered roots rather than
scanning the original 2^y domain.

The producer cancels nonlinear columns and tracks original-row combinations
with a descending pivot order. The checker directly multiplies original
coefficient columns by each witness, uses a different monomial order, and
recomputes affine rank in ascending variable order. They are separate shared
libraries with separate contexts. The shared header contains only the ABI.
Target-independent monomial layouts are reusable; coefficients and proofs
are fresh on every call.

The current bounds are 1..10 residual variables and 1..128 equations.
Nonzero original terms above degree two are explicitly unsupported. Duplicate
input terms XOR together. A packed witness has ceil(e/64) limbs, with unused
high bits rejected. Successful producer output is labelled "produced" until
checked independently. The checker returns the complete residual root set,
not a complete global Gröbner basis; full-query basis integration remains work.

Work limits, assignment limits and output capacity are explicit. An unsuccessful
call returns zero output count and does not modify the caller's output buffer.
The bounded work counter is defined in `plan.json`; it is not a complete CPU
operation count or an IC measurement. Budget exhaustion never returns a partial
root set as verified. An empty certificate remains complete enumeration.

This can reduce residual search when useful affine rank is present. It does
not remove fixed-variable branching, prove a general regularity bound, or
establish a novel asymptotic Gröbner algorithm. Larger complete-query use also
needs bounded residual-table memory and an independently verified full basis.

For k supplied witness rows, q=1+y+y(y-1)/2 quadratic features and
L=ceil(e/64) equation limbs, the current checker performs O(k*q*L) witness
parity work, O(y*k) machine-word affine row operations within its y<=10
bound, and O(2^(y-r)*(q*L+y)) assignment reconstruction and original-equation
evaluation. Sorting h discovered roots additionally takes O(h*log h)
comparisons. These are bounded residual costs after input normalization, not
the cost of producing a certificate or solving the complete original ideal.
If r is zero, the enumeration term retains its original exponential size.
Counting fewer assignments is useful only if construction and checking do
not consume the saved time. See `INTEGRATION.md` for the complete-query gates.
