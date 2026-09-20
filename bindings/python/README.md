# cryptanalysis (Python bindings)

Pure-Python `ctypes` bindings for **libcryptanalysis**, a C library of
discrete-logarithm algorithms: baby-step giant-step, parallel Pollard rho,
kangaroo, Bernstein-Lange grumpy giants, discrete logs with precomputation,
Pohlig-Hellman, Cheon's attack on
the strong Diffie-Hellman problem and index calculus in `(Z/pZ)^*`.  All
moduli are 64-bit (`p < 2^64`), so pass Python ints in range.

No third-party dependencies; Python >= 3.8.

## Getting the shared library

The package loads `libcryptanalysis.so` (or `.dylib`) from, in order:

1. the path in the `CRYPTANALYSIS_LIB` environment variable;
2. a copy inside the package directory (what `pip install .` produces);
3. `../../build/` relative to the package (a developer checkout built with
   CMake);
4. the system library path (`ctypes.util.find_library("cryptanalysis")`).

Developer checkout:

```sh
cmake -S ../.. -B ../../build -DCMAKE_BUILD_TYPE=Release && cmake --build ../../build -j
python3 -m unittest discover -s tests -v
```

Installation (compiles the C sources with the system C compiler into the
package; needs `cc` with `-std=gnu11` and `__int128`):

```sh
pip install .
```

## Example

```python
import cryptanalysis as ca

# order-q subgroup of Z_p^*, p = 2q + 1
g = ca.Group.zp(2000000579, 1000000289)
gen = g.find_generator(seed=1)
h = g.mul(gen, 123456789)

x, stats = g.dlog(gen, h)                       # Pohlig-Hellman + automatic solver
x, stats = g.rho(gen, h, ca.Options(threads=4)) # parallel Pollard rho
x, stats = g.kangaroo(gen, h, 123_000_000, 124_000_000)   # interval solvers
x, stats = g.grumpy(gen, h, 123_000_000, 124_000_000)
x, stats = g.bsgs(gen, h)
x, stats = g.precomp(gen, h, threads=4)        # ~n^2/3 precompute, ~n^1/3 online
print(x, stats.group_ops, stats.seconds)

# elliptic curve y^2 = x^3 + x + 7 over F_1000003
n = ca.Group.ec_count_points(1000003, 1, 7)
E = ca.Group.ec(1000003, 1, 7, n)
P = E.random_element(seed=3)          # element = (x, y, is_infinity, 0)
E.set_order(E.elem_order(P))
Q = E.mul(P, 4242)
print(E.dlog(P, Q)[0])                 # 4242 mod ord(P)

# Cheon's attack: recover alpha from g, alpha*g, alpha^d*g with d | q-1
d, cost = ca.cheon_best_divisor(1000000289)
ga, gad = g.cheon_instance(gen, 987654321, d)
alpha, stats = g.cheon(gen, ga, gad, d)

# index calculus in Z_p^*
y, ic_stats = ca.ic_solve(1099511627791, 3, 123456789)
assert pow(3, y, 1099511627791) == 123456789
ctx = ca.ICContext(1099511627791, 3)   # reuse the factor-base logs
print(ctx.log(424242))

# number theory helpers
ca.is_prime(1000003), ca.next_prime(10**6), ca.primitive_root(1000003)
ca.factorize(1000002)                 # [(2, 1), (3, 1), (166667, 1)]
```

Errors are raised as `cryptanalysis.CryptanalysisError` subclasses
(`InvalidError`, `NotFoundError`, `LimitError`, ...) carrying the C status
code and the library's error message.  `Group` objects are context managers
and release the native handle on `close()`.

## Layout

```
cryptanalysis/_lib.py     library loading, ctypes prototypes, struct-size checks
cryptanalysis/_types.py   Options / Stats / ICParams / ICStats dataclasses, enums
cryptanalysis/group.py    Group, elements, solvers, Cheon
cryptanalysis/indexcalc.py  ic_solve, ICContext
cryptanalysis/ntheory.py  is_prime, next_prime, primitive_root, powmod, invmod, factorize
tests/test_bindings.py    unittest suite (mirrors the C tests/test_ffi.c)
```

See `../../docs/FFI.md` for the underlying C ABI and `../../docs/ALGORITHMS.md`
for the mathematics.
