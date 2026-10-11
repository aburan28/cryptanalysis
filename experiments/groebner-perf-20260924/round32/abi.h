#pragma once
#include "../round31/abi.h"

struct CheckStats {
    uint64_t branches, contradictions, enumerated_branches, assignments;
    uint64_t roots, standard, work, workspace_bytes, proof_bytes, transform_xors;
    double specialization, contradiction_check, enumeration, basis_check;
};
#ifndef BRANCH_CHECK_ENUMERATION_BUDGET
#    define BRANCH_CHECK_ENUMERATION_BUDGET 4194304
#endif
#ifndef BRANCH_BASIS_PROOF_BUDGET
#    define BRANCH_BASIS_PROOF_BUDGET 1000000
#endif
