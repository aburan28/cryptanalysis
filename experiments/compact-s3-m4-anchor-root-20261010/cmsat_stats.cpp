#include <cstdint>
#include <cryptominisat5/cryptominisat.h>

extern "C" std::uint64_t q1427_last_conflicts(void *solver) {
    return static_cast<CMSat::SATSolver *>(solver)->get_last_conflicts();
}

extern "C" std::uint64_t q1427_last_propagations(void *solver) {
    return static_cast<CMSat::SATSolver *>(solver)->get_last_propagations();
}

extern "C" std::uint64_t q1427_last_decisions(void *solver) {
    return static_cast<CMSat::SATSolver *>(solver)->get_last_decisions();
}
