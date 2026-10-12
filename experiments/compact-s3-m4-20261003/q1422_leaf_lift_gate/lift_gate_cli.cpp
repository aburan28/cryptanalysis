// Bulk native lift-predicate preflight against checked Sage.
#include "lift_gate.hpp"

#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 2, "usage: lift_gate_cli FIELD");
        q1420::Field field(argv[1]);
        std::string encoded;
        while (std::cin >> encoded) {
            q1420::U128 x = q1420::parse_hex(encoded);
            std::cout << encoded << ' ' << int(q1422::curve_lifts(field, x))
                      << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
