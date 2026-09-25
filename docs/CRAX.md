# `crax`: the command line

`crax` is the toolkit's single entry point. It has one subcommand per attack.
The generic discrete-logarithm solvers run on the C library in `src/`. They
work over 64-bit groups and are the source of the measured constants in
[BENCHMARKS.md](BENCHMARKS.md). Everything else runs on the Rust attack suite
in [`suite/`](../suite/README.md), which uses arbitrary precision.

```sh
cd suite && cargo build --release --bin crax
./target/release/crax --help
```

The same binary is built by `make suite`.

**Conventions:**

- Every command accepts `--json`. It then prints exactly one JSON object on
  stdout.
- A command that reports an answer has checked that answer independently of
  the solver that produced it. For a discrete log, one scalar multiplication
  or exponentiation checks it. For a factor, a multiplication checks it. For a
  message, re-encryption checks it. The report says `"verified": true`, and an
  unverified answer exits non-zero.
- Problems can be given completely (`--g`, `--h`, `--q`), or generated from a
  planted secret (`--x`). With a planted secret, the report also says whether
  the planted value was recovered.
- Integers are decimal or `0x` hex. The factoring commands also accept
  expressions such as `2^227-1`, `(2^239+1)/3` or `3*10^40+7`.
- A size that an implementation cannot finish in reasonable time is refused,
  with the measured numbers, instead of being started. `--force` overrides
  this for the sieves and `--max-log2-ops` for the curve solvers.

## The command tree

| family | commands |
|---|---|
| discrete logs, generic (C library, p < 2^64) | `bsgs`, `rho`, `kangaroo`, `grumpy`, `precomp`, `glv`, `pohlig-hellman` (`ph`, `dlog`), `cheon`, `gpu-rho` |
| weak curves, any size | `ecdlp` (singular, Smart anomalous, Pohlig–Hellman, MOV/Frey–Rück) |
| factoring | `factor`, `gnfs`, `snfs`, `qs`, `ecm`, `pm1` (`--pp1`), `rho-factor` |
| RSA | `rsa fermat \| wiener \| from-d \| hastad \| common-modulus \| small-e \| batch-gcd` |
| index calculus | `ic zp` ((Z/pZ)^*, C library), `ic prime \| run \| compare \| fixed \| workflow \| boundary \| bench \| rho \| descent \| corpus \| budget \| ...`, `icx` |
| curves and challenges | `curve names \| info`, `challenge list \| show \| solve \| rho-job` |
| symmetric and hash | `list-ciphers`, `auto`, `boomerang`, `rectangle`, `sbox`, `aes-related-key`, `hash-auto`, `length-extension` |
| lattice and post-quantum | `mlwe` |
| isogenies | `isogeny` |
| distributed rho | `rho-collab` |
| demos and research bench | `visual-all`, `aes-visual-demo`, `bench`, `ec-challenges` |

The last five rows and `ic`/`icx` are the older research command lines:
`ca-suite`, `ca-ic` and `ca-icx`. `crax` passes their arguments through to
them unchanged, and their `--help`, flags and report formats are their own.
The old binary names still work.

## Discrete logarithms on the C library

```text
$ crax rho --p 2000000579 --order 1000000289 --x 123456789 --threads 2
rho: x = 123456789  (verified: g^x = h)
  group    Z_p^* p=2000000579 order=1000000289
  g        1422302461
  h        1216411080
  planted  recovered
  work     38523 group ops, 1063 table entries, 0.017 s, 2 thread(s), 1.218 ops/sqrt(width)

$ crax glv --curve glv-j0-26 --x 999999
glv-rho: x = 999999  (verified: g^x = h)
  group    E(F_p) p=67108933 a=0 b=7 order=16773703
  ...
  note     endomorphism J0: walk folded by an automorphism group of order 6 (rho speed-up 2.4495)

$ crax kangaroo --p 2000000579 --order 1000000289 --x 500123 --lo 500000 --hi 600000
$ crax cheon --p 2000000579 --order 1000000289 --alpha 987654321
$ crax ic zp --p 1099511627791 --g 3 --x 99
$ crax curve info --name glv-j0-26
```

Every solver checks on entry that both elements lie in the order-n subgroup.
A target outside ⟨g⟩ is refused at once; previously it made rho, glv, gpu-rho
and Pohlig–Hellman run forever. `kangaroo` bounds its walk at 128·√width
unless `--max-ops` is given, because a target outside the interval never
meets the tame herd.

## Weak curves of any size: `crax ecdlp`

`ecdlp` analyses a prime-field curve and then runs the cheapest attack whose
preconditions hold:

- the singular-cubic map to (F_p, +), F_p^\* or the norm-one torus;
- Smart's p-adic attack on anomalous curves;
- Pohlig–Hellman with BSGS / rho in each prime subgroup;
- on request, MOV / Frey–Rück to F_{p^k}^\* with a Tate pairing.

A curve without any of these weaknesses is refused, and the report gives the
reason for each check:

```text
$ crax ecdlp --curve p256 --x 5 --analyze-only
ecdlp on a 256-bit prime field: not solved
  Singular       no  4a³ + 27b² ≢ 0 (mod p): the curve is non-singular
  Smart          no  ord(G) ≠ p: not anomalous
  PohligHellman  no  ... largest prime factor 256 bits; Pohlig–Hellman needs ≈2^128.3 group operations (exceeds the 2^34 budget)
  Mov            no  embedding degree of the largest prime factor exceeds 12: MOV/Frey–Rück gives no usable transfer
```

MOV really does move the logarithm into F_{p^k}^\*. The finite-field solver
here is generic, though, not index calculus, so MOV is reported as a weakness
but never chosen on cost.

## The challenge corpus: `crax challenge`

`challenge solve <id>` reads what a record in
[`challenges/ecc/`](../challenges/ecc/README.md) says about its curve. That
includes the trace, embedding degree, endomorphism and subgroup order. From
that it picks an attack:

- the C library's GLV or Pohlig–Hellman solvers below 2^64;
- Smart for anomalous curves;
- the arbitrary-precision attacks above 2^64.

It then verifies the answer. On `check`-tier records it also compares the
answer with the stored log.

```text
$ crax challenge solve fp-anomalous-b128
fp-anomalous-b128 (open): x = 95065309868721090666590822693085299358 (verified: [x]G = target)
  curve    128-bit field, 128-bit subgroup = 170141183460469232383923901789557442567
  checks   anomalous=true embedding_degree=large endomorphism=anomalous
  method   Smart (0.062 s)
```

Measured over all 98 prime-field records in the corpus (release build, one
core, 180 s cap):

- **All 47 `check`-tier records with p > 3 solve** and match their stored logs.
- **Nine `open`-tier records solve.** None of these has a published answer.
  - Smart's attack handles the anomalous curves at 64, 96, 128 and 192 bits,
    in 0.02–0.15 s each.
  - Pohlig–Hellman handles a 160-bit class-number-2 CM curve (67 s) and two
    small ones.
  - GLV rho handles two 61-bit j = 0 curves.
- **The rest are refused, with reasons.** They have no structural weakness and
  their largest prime subgroup exceeds the budget.
- **One record, `fp-j0-b64-volcano5-h2`, has no answer.** Its target is not in
  ⟨G⟩: the C library and the weak-curve attacks agree independently. The two
  characteristic-3 records are outside the prime-field solver.

The budget is 2^44 group operations on the C library and 2^28 on the
arbitrary-precision attacks; raise it with `--max-log2-ops`.

## Factoring

```text
$ crax factor '2^128+1'
340282366920938463463374607431768211457 (39 digits) = 59649589127497217 * 5704689200685129054721
  complete, product verified (1.800 s)

$ crax snfs '2^227-1'
snfs: 2156795733...3727 (69 digits) = 26986333437777017 * 79921777382...8631  (verified)
  polynomial  x^4 - 2 (degree 4, m = 144115188075855872, skewness 1.19, alpha 1.92)
  factor base rational 6611 primes (B = 66289), algebraic 6605 ideals (B = 66289), 48 quadratic characters
  sieve       5808 lines, 134201 relations (5733 full, 128468 from partials)
  matrix      134201 x 165810 -> 22632 x 22599 after filtering, 32 dependencies; 3 square roots tried
  time        polyselect 0.00 s, sieve 5.76 s, linear algebra 0.79 s, sqrt 0.43 s, total 7.14 s

$ crax gnfs '1000000000000000000000007*100000000000000000000000000031'   # 54 digits, 11.8 s
$ crax qs <n>        # SIQS: 50 digits ~1 s, 60 digits ~16 s
$ crax ecm <n> --b1 11000 --curves 64
$ crax pm1 <n> --b1 100000 --b2 10000000      # --pp1 for Williams p+1
$ crax rho-factor <n>
```

These sieves are **educational scale**. They have no lattice sieve, no double
large primes, no Block Lanczos and no Kleinjung polynomial selection. At every
size both can reach, the quadratic sieve here beats GNFS, so `factor` uses the
QS up to 100 digits. Sizes where a sieve is impractical are refused unless
`--force` is given: GNFS above 65 digits, SNFS above 90 and the QS above 75.
The measured timings and the full list of limitations are in the module
documentation of `suite/src/cryptanalysis/factoring/`.

## RSA

```text
$ crax rsa wiener <n> --e <e>
wiener: n = 100838969382656946560373176440817955492681622693031250224486320217033755381847 * 105521954077741822635373266291794581792811894718351891228448572712095560074597 (verified) (38 iterations, 0.000 s)
  d = 3339107582246289661

$ crax rsa hastad --e 3 <c1>:<n1> <c2>:<n2> <c3>:<n3>
hastad-broadcast: m = 1976620216402300889624482718775150 (verified: re-encrypts to the ciphertext) (0.001 s)
  as text: attack at dawn

$ crax rsa fermat <n>
$ crax rsa batch-gcd <n1> <n2> ... | @moduli.txt
$ crax rsa from-d <n> --e <e> --d <d>
$ crax rsa common-modulus --n <n> --e1 .. --c1 .. --e2 .. --c2 ..
$ crax rsa small-e --n <n> --e 3 --c <c>
```
