// Two independent inversion chains, preserving one inverse per 16 points.
#pragma once
namespace eccPacked131 {
#include "fixed_sigma.h"
struct Goal22FieldPair { P131 first, second; };
ECC_HD Goal22FieldPair goal22NormalPairMul(Goal22FieldPair a, Goal22FieldPair b) {
    const P131 a0=toPolynomial131(a.first),a1=toPolynomial131(a.second);
    const P131 b0=toPolynomial131(b.first),b1=toPolynomial131(b.second);
    uint32_t h0[9],h1[9];
    product131(a0,b0,h0); product131(a1,b1,h1);
    return {fromPolynomialProduct131(h0),fromPolynomialProduct131(h1)};
}
ECC_HD Goal22FieldPair goal22PairSquare(Goal22FieldPair a) {
    return {sqr131(a.first),sqr131(a.second)};
}
template<int K> ECC_HD Goal22FieldPair goal22PairFrobenius(Goal22FieldPair a) {
    if constexpr(K==4)return {goal22Sigma4(a.first),goal22Sigma4(a.second)};
    if constexpr(K==8)return {goal22Sigma8(a.first),goal22Sigma8(a.second)};
    if constexpr(K==16)return {goal22Sigma16(a.first),goal22Sigma16(a.second)};
    if constexpr(K==32)return {goal22Sigma32(a.first),goal22Sigma32(a.second)};
    if constexpr(K==65)return {goal22Sigma65(a.first),goal22Sigma65(a.second)};
}
ECC_HD Goal22FieldPair goal22PairedInverse(Goal22FieldPair a) {
    Goal22FieldPair acc=goal22NormalPairMul(goal22PairSquare(a),a);
    acc=goal22NormalPairMul(goal22PairSquare(goal22PairSquare(acc)),acc);
    acc=goal22NormalPairMul(goal22PairFrobenius<4>(acc),acc);
    acc=goal22NormalPairMul(goal22PairFrobenius<8>(acc),acc);
    acc=goal22NormalPairMul(goal22PairFrobenius<16>(acc),acc);
    acc=goal22NormalPairMul(goal22PairFrobenius<32>(acc),acc);
    acc=goal22NormalPairMul(goal22PairSquare(acc),a);
    acc=goal22NormalPairMul(goal22PairFrobenius<65>(acc),acc);
    return goal22PairSquare(acc);
}
} // namespace eccPacked131
