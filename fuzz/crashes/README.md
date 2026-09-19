# Findings

Reproducers for library defects the harnesses (or a targeted probe built from
them) hit.  Nothing in this directory is part of the seed corpus, so the CI
job never replays it - the workflow only reads `fuzz/corpus/`.

**All three are fixed.**  Each `.txt` opens with the fix and the regression
test that pins it.  The files stay because the reproducers are worth keeping
and because they record what the harnesses' restrictions used to be for.

Each `.bin` is a raw input for the harness named in the matching `.txt`.
Two of the three need the harness's guard rails removed:

```sh
# build with the parameter clamps disabled
CC=clang CFLAGS="-fsanitize=fuzzer-no-link,address,undefined -DCA_FUZZ_WILD_PARAMS" \
  cmake -S . -B build-wild -DCA_FUZZ=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-wild -j4
UBSAN_OPTIONS=halt_on_error=1 ./build-wild/fuzz_dlog fuzz/crashes/<input>.bin
```

| file | affected API | class |
| --- | --- | --- |
| `grumpy_kangaroo_out_of_interval.*` | `ca_grumpy_solve`, `ca_kangaroo_solve` | wrong result (outside the requested interval) |
| `rho_kangaroo_dp_bits_shift.*` | `ca_rho_solve`, `ca_kangaroo_solve` | undefined behaviour (shift >= width) |
| `kangaroo_herd_size_hang.*` | `ca_kangaroo_solve` | infinite loop (denial of service) |
