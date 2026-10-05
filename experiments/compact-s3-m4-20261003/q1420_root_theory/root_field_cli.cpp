// Simple independent executable for comparing C++ roots with checked Sage.
#include "root_field.hpp"

#include <iostream>

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 4, "usage: root_field_cli FIELD LEFT_HEX RIGHT_HEX");
        q1420::Field field(argv[1]);
        auto roots = field.roots_onb(q1420::parse_hex(argv[2]),
                                    q1420::parse_hex(argv[3]));
        for (auto root : roots) std::cout << q1420::hex(root) << "\n";
        std::cerr << "mul=" << field.counts.mul << " sqr=" << field.counts.sqr
                  << " inv=" << field.counts.inv << "\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
