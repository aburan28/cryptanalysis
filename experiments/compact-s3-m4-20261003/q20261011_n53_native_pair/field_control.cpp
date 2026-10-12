// Exact-source arithmetic oracle adapter for Q1454 native_field53.hpp.
#include "native_field53.hpp"
int main() {
    std::string a, b, c, d;
    while (std::cin >> a >> b >> c >> d) {
        U x = readhex(a), y = readhex(b);
        P p{x, y, false}, q{readhex(c), readhex(d), false};
        P sum = add(p, q);
        Key key = canonical(sum);
        std::cout << hex(mul(x, y)) << ' ' << hex(sqr(x)) << ' ' << hex(inv(x))
                  << ' ' << (sum.inf ? "I" : hex(sum.x))
                  << ' ' << (sum.inf ? "I" : hex(sum.y))
                  << ' ' << (sum.inf ? "I" : hex(key.value))
                  << ' ' << key.exponent << ' ' << key.sign << '\n';
    }
}
