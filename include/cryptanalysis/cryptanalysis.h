/*
 * cryptanalysis.h - umbrella header for libcryptanalysis.
 *
 * A toolkit of discrete-logarithm algorithms written against a generic
 * cyclic-group interface, with concrete groups for (Z/pZ)^* and elliptic
 * curves over prime fields (64-bit moduli):
 *
 *   ca_bsgs.h       baby-step giant-step (Shanks), amortised tables
 *   ca_rho.h        parallel Pollard rho, distinguished points, negation map
 *   ca_kangaroo.h   Pollard kangaroo / lambda for interval logs
 *   ca_grumpy.h     Bernstein-Lange "two grumpy giants and a baby"
 *   ca_pohlig.h     Pohlig-Hellman reduction and the ca_dlog driver
 *   ca_cheon.h      Cheon's attack on the strong Diffie-Hellman problem
 *   ca_indexcalc.h  index calculus in (Z/pZ)^* (linear sieve, Lanczos)
 *   ca_gpu.h        CUDA Pollard rho (with a host emulator backend)
 *   ca_coord.h      distributed rho: a coordinator with a URL, agents that
 *                   dial out to it and are pushed to over the same socket
 *   ca_ffi.h        flat C ABI used by the Rust, Go and Python bindings
 */
#ifndef CRYPTANALYSIS_H
#define CRYPTANALYSIS_H

#include "ca_types.h"
#include "ca_modarith.h"
#include "ca_group.h"
#include "ca_bsgs.h"
#include "ca_rho.h"
#include "ca_kangaroo.h"
#include "ca_grumpy.h"
#include "ca_pohlig.h"
#include "ca_cheon.h"
#include "ca_indexcalc.h"
#include "ca_gpu.h"
#include "ca_coord.h"
#include "ca_ffi.h"

#endif /* CRYPTANALYSIS_H */
