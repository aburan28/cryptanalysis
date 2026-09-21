//! **Curve zoo** — every standardised short-Weierstrass prime-field
//! curve we know about, exposed as [`CurveParams`] constructors.
//!
//! The cheat-sheet for who-uses-what:
//!
//! | Region / Standard                            | Curves                                     |
//! |----------------------------------------------|--------------------------------------------|
//! | Germany / Austria / Switzerland (regulated)  | Brainpool 192…512 r1                       |
//! | France (ANSSI government)                    | FRP256v1 + Brainpool                       |
//! | Russia / EAEU (GOST R 34.10)                 | CryptoPro A/B/C (256-bit) + tc26 paramSetA/B (512-bit) |
//! | China (GB/T 32918)                           | SM2 (see [`CurveParams::sm2`])             |
//! | Historical Internet standards                | secp112/128/160*, P-192 (legacy, low security) |
//! | South Korea (EC-KCDSA / TTA)                 | NIST / SECG                                |
//! | Japan (CRYPTREC)                             | NIST / SECG                                |
//! | Brazil (ICP-Brasil)                          | NIST + Brainpool                           |
//! | UK / Canada / AU / NZ (Five Eyes)            | NIST / SECG                                |
//! | Latin America, SE Asia                       | NIST / SECG                                |
//!
//! Every curve below is in short-Weierstrass form `y² = x³ + ax + b
//! (mod p)` with prime-subgroup order `n` and cofactor `h`.  All the
//! generic arithmetic (`Point::scalar_mul`, `Point::scalar_mul_ct`,
//! `Point::add`, `Point::double`, `CurveParams::is_on_curve`) works on
//! these curves the moment they're constructed.

use super::curve::CurveParams;
use num_bigint::BigUint;

impl CurveParams {
    // ── Historical low-security SECG/NIST curves ───────────────────────────

    /// **secp112r1** (SEC 2 v1 §2.2.1).
    ///
    /// WTLS/WAP-era 112-bit prime-field curve with roughly 56-bit
    /// generic ECDLP security.  Included for legacy audits only.
    pub fn secp112r1() -> Self {
        CurveParams {
            name: "secp112r1",
            p: hexp("DB7C2ABF62E35E668076BEAD208B"),
            a: hexp("DB7C2ABF62E35E668076BEAD2088"),
            b: hexp("659EF8BA043916EEDE8911702B22"),
            gx: hexp("09487239995A5EE76B55F9C2F098"),
            gy: hexp("A89CE5AF8724C0A23E0E0FF77500"),
            n: hexp("DB7C2ABF62E35E7628DFAC6561C5"),
            h: 1,
        }
    }

    /// **secp112r2** (SEC 2 v1 §2.2.2).
    ///
    /// WTLS/WAP-era 112-bit prime-field curve with cofactor 4 and
    /// roughly 56-bit generic ECDLP security.  Included for legacy
    /// audits only.
    pub fn secp112r2() -> Self {
        CurveParams {
            name: "secp112r2",
            p: hexp("DB7C2ABF62E35E668076BEAD208B"),
            a: hexp("6127C24C05F38A0AAAF65C0EF02C"),
            b: hexp("51DEF1815DB5ED74FCC34C85D709"),
            gx: hexp("4BA30AB5E892B4E1649DD0928643"),
            gy: hexp("ADCD46F5882E3747DEF36E956E97"),
            n: hexp("36DF0AAFD8B8D7597CA10520D04B"),
            h: 4,
        }
    }

    /// **secp128r1** (SEC 2 v1 §2.3.1).
    ///
    /// WTLS/WAP-era 128-bit prime-field curve with roughly 64-bit
    /// generic ECDLP security.  Included for legacy audits only.
    pub fn secp128r1() -> Self {
        CurveParams {
            name: "secp128r1",
            p: hexp("FFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFF"),
            a: hexp("FFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFC"),
            b: hexp("E87579C11079F43DD824993C2CEE5ED3"),
            gx: hexp("161FF7528B899B2D0C28607CA52C5B86"),
            gy: hexp("CF5AC8395BAFEB13C02DA292DDED7A83"),
            n: hexp("FFFFFFFE0000000075A30D1B9038A115"),
            h: 1,
        }
    }

    /// **secp128r2** (SEC 2 v1 §2.3.2).
    ///
    /// WTLS/WAP-era 128-bit prime-field curve with cofactor 4 and
    /// roughly 64-bit generic ECDLP security.  Included for legacy
    /// audits only.
    pub fn secp128r2() -> Self {
        CurveParams {
            name: "secp128r2",
            p: hexp("FFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFF"),
            a: hexp("D6031998D1B3BBFEBF59CC9BBFF9AEE1"),
            b: hexp("5EEEFCA380D02919DC2C6558BB6D8A5D"),
            gx: hexp("7B6AA5D85E572983E6FB32A7CDEBC140"),
            gy: hexp("27B6916A894D3AEE7106FE805FC34B44"),
            n: hexp("3FFFFFFF7FFFFFFFBE0024720613B5A3"),
            h: 4,
        }
    }

    /// **secp160k1** (SEC 2 v2 §2.1.1).
    ///
    /// Legacy 160-bit prime-field Koblitz curve, roughly 80-bit generic
    /// ECDLP security.  Kept for historical audits and attack demos only;
    /// do not use for new systems.
    pub fn secp160k1() -> Self {
        CurveParams {
            name: "secp160k1",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC73"),
            a: BigUint::from(0u32),
            b: BigUint::from(7u32),
            gx: hexp("3B4C382CE37AA192A4019E763036F4F5DD4D7EBB"),
            gy: hexp("938CF935318FDCED6BC28286531733C3F03C4FEE"),
            n: hexp("0100000000000000000001B8FA16DFAB9ACA16B6B3"),
            h: 1,
        }
    }

    /// **secp160r1** (SEC 2 v2 §2.1.2).
    ///
    /// Legacy random 160-bit prime-field curve, roughly 80-bit generic
    /// ECDLP security.  Present for historical interoperability analysis
    /// and cryptanalytic regression tests, not production use.
    pub fn secp160r1() -> Self {
        CurveParams {
            name: "secp160r1",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFF"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFC"),
            b: hexp("1C97BEFC54BD7A8B65ACF89F81D4D4ADC565FA45"),
            gx: hexp("4A96B5688EF573284664698968C38BB913CBFC82"),
            gy: hexp("23A628553168947D59DCC912042351377AC5FB32"),
            n: hexp("0100000000000000000001F4C8F927AED3CA752257"),
            h: 1,
        }
    }

    /// **secp160r2** (SEC 2 v2 §2.1.3).
    ///
    /// Legacy random 160-bit prime-field curve, roughly 80-bit generic
    /// ECDLP security.  Kept to model historically deployed standards;
    /// modern deployments should use >=128-bit-security curves instead.
    pub fn secp160r2() -> Self {
        CurveParams {
            name: "secp160r2",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC73"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC70"),
            b: hexp("B4E134D3FB59EB8BAB57274904664D5AF50388BA"),
            gx: hexp("52DCB034293A117E1F4FF11B30F7199D3144CE6D"),
            gy: hexp("FEAFFEF2E331F296E071FA0DF9982CFEA7D43F2E"),
            n: hexp("0100000000000000000000351EE786A818F3A1A16B"),
            h: 1,
        }
    }

    // ── Brainpool (RFC 5639) ────────────────────────────────────────────────

    /// **brainpoolP192r1** (RFC 5639 §3.1).
    pub fn brainpool_p192r1() -> Self {
        CurveParams {
            name: "brainpoolP192r1",
            p: hexp("C302F41D932A36CDA7A3463093D18DB78FCE476DE1A86297"),
            a: hexp("6A91174076B1E0E19C39C031FE8685C1CAE040E5C69A28EF"),
            b: hexp("469A28EF7C28CCA3DC721D044F4496BCCA7EF4146FBF25C9"),
            gx: hexp("C0A0647EAAB6A48753B033C56CB0F0900A2F5C4853375FD6"),
            gy: hexp("14B690866ABD5BB88B5F4828C1490002E6773FA2FA299B8F"),
            n: hexp("C302F41D932A36CDA7A3462F9E9E916B5BE8F1029AC4ACC1"),
            h: 1,
        }
    }

    /// **brainpoolP224r1** (RFC 5639 §3.2).
    pub fn brainpool_p224r1() -> Self {
        CurveParams {
            name: "brainpoolP224r1",
            p: hexp("D7C134AA264366862A18302575D1D787B09F075797DA89F57EC8C0FF"),
            a: hexp("68A5E62CA9CE6C1C299803A6C1530B514E182AD8B0042A59CAD29F43"),
            b: hexp("2580F63CCFE44138870713B1A92369E33E2135D266DBB372386C400B"),
            gx: hexp("0D9029AD2C7E5CF4340823B2A87DC68C9E4CE3174C1E6EFDEE12C07D"),
            gy: hexp("58AA56F772C0726F24C6B89E4ECDAC24354B9E99CAA3F6D3761402CD"),
            n: hexp("D7C134AA264366862A18302575D0FB98D116BC4B6DDEBCA3A5A7939F"),
            h: 1,
        }
    }

    /// **brainpoolP256r1** (RFC 5639 §3.3).
    pub fn brainpool_p256r1() -> Self {
        CurveParams {
            name: "brainpoolP256r1",
            p: hexp("A9FB57DBA1EEA9BC3E660A909D838D726E3BF623D52620282013481D1F6E5377"),
            a: hexp("7D5A0975FC2C3057EEF67530417AFFE7FB8055C126DC5C6CE94A4B44F330B5D9"),
            b: hexp("26DC5C6CE94A4B44F330B5D9BBD77CBF958416295CF7E1CE6BCCDC18FF8C07B6"),
            gx: hexp("8BD2AEB9CB7E57CB2C4B482FFC81B7AFB9DE27E1E3BD23C23A4453BD9ACE3262"),
            gy: hexp("547EF835C3DAC4FD97F8461A14611DC9C27745132DED8E545C1D54C72F046997"),
            n: hexp("A9FB57DBA1EEA9BC3E660A909D838D718C397AA3B561A6F7901E0E82974856A7"),
            h: 1,
        }
    }

    /// **brainpoolP320r1** (RFC 5639 §3.4).
    pub fn brainpool_p320r1() -> Self {
        CurveParams {
            name: "brainpoolP320r1",
            p: hexp(
                "D35E472036BC4FB7E13C785ED201E065F98FCFA6F6F40DEF4F92B9EC7893EC28FCD412B1F1B32E27",
            ),
            a: hexp(
                "3EE30B568FBAB0F883CCEBD46D3F3BB8A2A73513F5EB79DA66190EB085FFA9F492F375A97D860EB4",
            ),
            b: hexp(
                "520883949DFDBC42D3AD198640688A6FE13F41349554B49ACC31DCCD884539816F5EB4AC8FB1F1A6",
            ),
            gx: hexp(
                "43BD7E9AFB53D8B85289BCC48EE5BFE6F20137D10A087EB6E7871E2A10A599C710AF8D0D39E20611",
            ),
            gy: hexp(
                "14FDD05545EC1CC8AB4093247F77275E0743FFED117182EAA9C77877AAAC6AC7D35245D1692E8EE1",
            ),
            n: hexp(
                "D35E472036BC4FB7E13C785ED201E065F98FCFA5B68F12A32D482EC7EE8658E98691555B44C59311",
            ),
            h: 1,
        }
    }

    /// **brainpoolP384r1** (RFC 5639 §3.5).
    pub fn brainpool_p384r1() -> Self {
        CurveParams {
            name: "brainpoolP384r1",
            p: hexp("8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B412B1DA197FB71123ACD3A729901D1A71874700133107EC53"),
            a: hexp("7BC382C63D8C150C3C72080ACE05AFA0C2BEA28E4FB22787139165EFBA91F90F8AA5814A503AD4EB04A8C7DD22CE2826"),
            b: hexp("04A8C7DD22CE28268B39B55416F0447C2FB77DE107DCD2A62E880EA53EEB62D57CB4390295DBC9943AB78696FA504C11"),
            gx: hexp("1D1C64F068CF45FFA2A63A81B7C13F6B8847A3E77EF14FE3DB7FCAFE0CBD10E8E826E03436D646AAEF87B2E247D4AF1E"),
            gy: hexp("8ABE1D7520F9C2A45CB1EB8E95CFD55262B70B29FEEC5864E19C054FF99129280E4646217791811142820341263C5315"),
            n: hexp("8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B31F166E6CAC0425A7CF3AB6AF6B7FC3103B883202E9046565"),
            h: 1,
        }
    }

    /// **brainpoolP512r1** (RFC 5639 §3.7).
    pub fn brainpool_p512r1() -> Self {
        CurveParams {
            name: "brainpoolP512r1",
            p: hexp("AADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA703308717D4D9B009BC66842AECDA12AE6A380E62881FF2F2D82C68528AA6056583A48F3"),
            a: hexp("7830A3318B603B89E2327145AC234CC594CBDD8D3DF91610A83441CAEA9863BC2DED5D5AA8253AA10A2EF1C98B9AC8B57F1117A72BF2C7B9E7C1AC4D77FC94CA"),
            b: hexp("3DF91610A83441CAEA9863BC2DED5D5AA8253AA10A2EF1C98B9AC8B57F1117A72BF2C7B9E7C1AC4D77FC94CADC083E67984050B75EBAE5DD2809BD638016F723"),
            gx: hexp("81AEE4BDD82ED9645A21322E9C4C6A9385ED9F70B5D916C1B43B62EEF4D0098EFF3B1F78E2D0D48D50D1687B93B97D5F7C6D5047406A5E688B352209BCB9F822"),
            gy: hexp("7DDE385D566332ECC0EABFA9CF7822FDF209F70024A57B1AA000C55B881F8111B2DCDE494A5F485E5BCA4BD88A2763AED1CA2B2FA8F0540678CD1E0F3AD80892"),
            n: hexp("AADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA70330870553E5C414CA92619418661197FAC10471DB1D381085DDADDB58796829CA90069"),
            h: 1,
        }
    }

    // ── French ANSSI (Publication FRP256v1) ─────────────────────────────────

    /// **FRP256v1** — the French ANSSI 256-bit curve.  Mandatory for
    /// French government use (RGS qualified) and accepted by the
    /// French eIDAS-qualified PKI.
    pub fn frp256v1() -> Self {
        CurveParams {
            name: "FRP256v1",
            p: hexp("F1FD178C0B3AD58F10126DE8CE42435B3961ADBCABC8CA6DE8FCF353D86E9C03"),
            a: hexp("F1FD178C0B3AD58F10126DE8CE42435B3961ADBCABC8CA6DE8FCF353D86E9C00"),
            b: hexp("EE353FCA5428A9300D4ABA754A44C00FDFEC0C9AE4B1A1803075ED967B7BB73F"),
            gx: hexp("B6B3D4C356C139EB31183D4749D423958C27D2DCAF98B70164C97A2DD98F5CFF"),
            gy: hexp("6142E0F7C8B204911F9271F0F3ECEF8C2701C307E8E4C9E183115A1554062CFB"),
            n: hexp("F1FD178C0B3AD58F10126DE8CE42435B53DC67E140D2BF941FFDD459C6D655E1"),
            h: 1,
        }
    }

    // ── NIST P-curves (FIPS 186-4, SEC2 v2) ─────────────────────────────────

    /// **NIST P-192 / secp192r1 / ANSI prime192v1** (FIPS 186-4 §D.2.1).
    ///
    /// Legacy 192-bit curve with roughly 96-bit generic ECDLP security.
    /// Included for historical Internet-standard audits, not new systems.
    pub fn p192() -> Self {
        CurveParams {
            name: "P-192",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFF"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFC"),
            b: hexp("64210519E59C80E70FA7E9AB72243049FEB8DEECC146B9B1"),
            gx: hexp("188DA80EB03090F67CBF20EB43A18800F4FF0AFD82FF1012"),
            gy: hexp("07192B95FFC8DA78631011ED6B24CDD573F977A11E794811"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFF99DEF836146BC9B1B4D22831"),
            h: 1,
        }
    }

    /// Alias for [`CurveParams::p192`] using the SECG name.
    pub fn secp192r1() -> Self {
        Self::p192()
    }

    /// Alias for [`CurveParams::p192`] using the ANSI X9.62 name.
    pub fn prime192v1() -> Self {
        Self::p192()
    }

    /// **NIST P-224 / secp224r1 / ANSI prime224v1** (FIPS 186-4 §D.2.2).
    pub fn p224() -> Self {
        CurveParams {
            name: "P-224",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF000000000000000000000001"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFE"),
            b: hexp("B4050A850C04B3ABF54132565044B0B7D7BFD8BA270B39432355FFB4"),
            gx: hexp("B70E0CBD6BB4BF7F321390B94A03C1D356C21122343280D6115C1D21"),
            gy: hexp("BD376388B5F723FB4C22DFE6CD4375A05A07476444D5819985007E34"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFF16A2E0B8F03E13DD29455C5C2A3D"),
            h: 1,
        }
    }

    /// **NIST P-384 / secp384r1** (FIPS 186-4 §D.2.4).
    pub fn p384() -> Self {
        CurveParams {
            name: "P-384",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFF"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFC"),
            b: hexp("B3312FA7E23EE7E4988E056BE3F82D19181D9C6EFE8141120314088F5013875AC656398D8A2ED19D2A85C8EDD3EC2AEF"),
            gx: hexp("AA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A385502F25DBF55296C3A545E3872760AB7"),
            gy: hexp("3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C00A60B1CE1D7E819D7A431D7C90EA0E5F"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973"),
            h: 1,
        }
    }

    /// **NIST P-521 / secp521r1** (FIPS 186-4 §D.2.5).  Field prime is
    /// the Mersenne prime `2^521 − 1`.  Hex literals here are exactly
    /// 131 nibbles wide (= 521 bits, leading nibble `1`).
    pub fn p521() -> Self {
        CurveParams {
            name: "P-521",
            p: hexp("1FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
            a: hexp("1FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC"),
            b: hexp("51953EB9618E1C9A1F929A21A0B68540EEA2DA725B99B315F3B8B489918EF109E156193951EC7E937B1652C0BD3BB1BF073573DF883D2C34F1EF451FD46B503F00"),
            gx: hexp("C6858E06B70404E9CD9E3ECB662395B4429C648139053FB521F828AF606B4D3DBAA14B5E77EFE75928FE1DC127A2FFA8DE3348B3C1856A429BF97E7E31C2E5BD66"),
            gy: hexp("11839296A789A3BC0045C8A5FB42C7D1BD998F54449579B446817AFBD17273E662C97EE72995EF42640C550B9013FAD0761353C7086A272C24088BE94769FD16650"),
            n: hexp("1FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFA51868783BF2F966B7FCC0148F709A5D03BB5C9B8899C47AEBB6FB71E91386409"),
            h: 1,
        }
    }

    // ── SECG Koblitz curves ─────────────────────────────────────────────────

    /// **secp192k1** — Koblitz curve over a 192-bit prime, j = 0,
    /// `y² = x³ + 3 (mod p)`.  SEC2 v2 §2.2.1.
    pub fn secp192k1() -> Self {
        CurveParams {
            name: "secp192k1",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFEE37"),
            a: BigUint::from(0u32),
            b: BigUint::from(3u32),
            gx: hexp("DB4FF10EC057E9AE26B07D0280B7F4341DA5D1B1EAE06C7D"),
            gy: hexp("9B2F2F6D9C5628A7844163D015BE86344082AA88D95E2F9D"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFE26F2FC170F69466A74DEFD8D"),
            h: 1,
        }
    }

    /// **secp224k1** — Koblitz curve over the 224-bit prime
    /// `p = 2²²⁴ − 2³² − 0x1A93`.  `y² = x³ + 5 (mod p)`.  SEC2 v2
    /// §2.3.1.  Group order is a 225-bit prime (one bit larger than
    /// the field), so cofactor h = 1.
    pub fn secp224k1() -> Self {
        CurveParams {
            name: "secp224k1",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFE56D"),
            a: BigUint::from(0u32),
            b: BigUint::from(5u32),
            gx: hexp("A1455B334DF099DF30FC28A169A467E9E47075A90F7E650EB6B7A45C"),
            gy: hexp("7E089FED7FBA344282CAFBD6F7E319F7C0B0BD59E2CA4BDB556D61A5"),
            n: hexp("010000000000000000000000000001DCE8D2EC6184CAF0A971769FB1F7"),
            h: 1,
        }
    }

    // ── Russian GOST R 34.10-2012 operational parameter sets ────────────────

    /// **id-GostR3410-2001-CryptoPro-A-ParamSet** (RFC 4357 §11.4.3) —
    /// the canonical 256-bit GOST 34.10 curve used by virtually every
    /// Russian commercial PKI.  Equally valid for GOST R 34.10-2012-256.
    pub fn gost_cryptopro_a() -> Self {
        CurveParams {
            name: "GOST-CryptoPro-A",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD97"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD94"),
            b: BigUint::from(0xA6u32),
            gx: BigUint::from(1u32),
            gy: hexp("8D91E471E0989CDA27DF505A453F2B7635294F2DDF23E3B122ACC99C9E9F1E14"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF6C611070995AD10045841B09B761B893"),
            h: 1,
        }
    }

    /// **id-GostR3410-2001-CryptoPro-B-ParamSet** (RFC 4357 §11.4.4).
    pub fn gost_cryptopro_b() -> Self {
        CurveParams {
            name: "GOST-CryptoPro-B",
            p: hexp("8000000000000000000000000000000000000000000000000000000000000C99"),
            a: hexp("8000000000000000000000000000000000000000000000000000000000000C96"),
            b: hexp("3E1AF419A269A5F866A7D3C25C3DF80AE979259373FF2B182F49D4CE7E1BBC8B"),
            gx: BigUint::from(1u32),
            gy: hexp("3FA8124359F96680B83D1C3EB2C070E5C545C9858D03ECFB744BF8D717717EFC"),
            n: hexp("800000000000000000000000000000015F700CFFF1A624E5E497161BCC8A198F"),
            h: 1,
        }
    }

    /// **id-GostR3410-2001-CryptoPro-C-ParamSet** (RFC 4357 §11.4.5).
    pub fn gost_cryptopro_c() -> Self {
        CurveParams {
            name: "GOST-CryptoPro-C",
            p: hexp("9B9F605F5A858107AB1EC85E6B41C8AACF846E86789051D37998F7B9022D759B"),
            a: hexp("9B9F605F5A858107AB1EC85E6B41C8AACF846E86789051D37998F7B9022D7598"),
            b: hexp("805A"),
            gx: BigUint::from(0u32),
            gy: hexp("41ECE55743711A8C3CBF3783CD08C0EE4D4DC440D4641A8F366E550DFDB3BB67"),
            n: hexp("9B9F605F5A858107AB1EC85E6B41C8AA582CA3511EDDFB74F02F3A6598980BB9"),
            h: 1,
        }
    }

    /// **id-tc26-gost-3410-12-512-paramSetA** (RFC 7836 §B.3) — the
    /// canonical 512-bit GOST R 34.10-2012 curve.  Field prime is
    /// `2⁵¹² − 569` (ends in `…FDC7`, not `…FFC7`).
    pub fn gost_tc26_512_a() -> Self {
        CurveParams {
            name: "GOST-tc26-512-paramSetA",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFDC7"),
            a: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFDC4"),
            b: hexp("E8C2505DEDFC86DDC1BD0B2B6667F1DA34B82574761CB0E879BD081CFD0B6265EE3CB090F30D27614CB4574010DA90DD862EF9D4EBEE4761503190785A71C760"),
            gx: BigUint::from(3u32),
            gy: hexp("7503CFE87A836AE3A61B8816E25450E6CE5E1C93ACF1ABC1778064FDCBEFA921DF1626BE4FD036E93D75E6A50E3A41E98028FE5FC235F5B889A589CB5215F2A4"),
            n: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF27E69532F48D89116FF22B8D4E0560609B4B38ABFAD2B85DCACDB1411F10B275"),
            h: 1,
        }
    }

    /// **id-tc26-gost-3410-2012-256-paramSetA** (RFC 7836 §B.1) — the
    /// 2012-specific 256-bit curve (distinct from the older CryptoPro-A
    /// curve which is renamed paramSetB in the 2012 standard).  Has a
    /// non-trivial `a`/`b`.
    pub fn gost_tc26_256_a() -> Self {
        CurveParams {
            name: "GOST-tc26-256-paramSetA",
            p: hexp("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD97"),
            a: hexp("C2173F1513981673AF4892C23035A27CE25E2013BF95AA33B22C656F277E7335"),
            b: hexp("295F9BAE7428ED9CCC20E7C359A9D41A22FCCD9108E17BF7BA9337A6F8AE9513"),
            gx: hexp("91E38443A5E82C0D880923425712B2BB658B9196932E02C78B2582FE742DAA28"),
            gy: hexp("32879423AB1A0375895786C4BB46E9565FDE0B5344766740AF268ADB32322E5C"),
            n: hexp("400000000000000000000000000000000FD8CDDFC87B6635C115AF556C360C67"),
            h: 1,
        }
    }

    /// **id-tc26-gost-3410-12-512-paramSetB** (RFC 7836 §B.4).
    pub fn gost_tc26_512_b() -> Self {
        CurveParams {
            name: "GOST-tc26-512-paramSetB",
            p: hexp("8000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006F"),
            a: hexp("8000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006C"),
            b: hexp("687D1B459DC841457E3E06CF6F5E2517B97C7D614AF138BCBF85DC806C4B289F3E965D2DB1416D217F8B276FAD1AB69C50F78BEE1FA3106EFB8CCBC7C5140116"),
            gx: BigUint::from(2u32),
            gy: hexp("1A8F7EDA389B094C2C071E3647A8940F3C123B697578C213BE6DD9E6C8EC7335DCB228FD1EDF4A39152CBCAAF8C0398828041055F94CEEEC7E21340780FE41BD"),
            n: hexp("800000000000000000000000000000000000000000000000000000000000000149A1EC142565A545ACFDB77BD9D40CFA8B996712101BEA0EC6346C54374F25BD"),
            h: 1,
        }
    }
}

/// Parse a big-endian hex string into a `BigUint`.  Panics on malformed
/// input — this is only used at curve-construction time on fixed
/// literals.
fn hexp(s: &str) -> BigUint {
    BigUint::parse_bytes(s.as_bytes(), 16)
        .unwrap_or_else(|| panic!("curve_zoo: invalid hex literal {:?}", s))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::point::Point;
    use num_bigint::BigUint;
    use num_traits::Zero;

    /// Every curve's generator satisfies the curve equation.  This is
    /// the cheapest non-trivial structural check; if anyone fat-fingers
    /// a hex constant, it falls over here.
    #[test]
    fn all_curve_generators_on_curve() {
        let curves = [
            CurveParams::brainpool_p192r1(),
            CurveParams::brainpool_p224r1(),
            CurveParams::brainpool_p256r1(),
            CurveParams::brainpool_p320r1(),
            CurveParams::brainpool_p384r1(),
            CurveParams::brainpool_p512r1(),
            CurveParams::frp256v1(),
            CurveParams::secp112r1(),
            CurveParams::secp112r2(),
            CurveParams::secp128r1(),
            CurveParams::secp128r2(),
            CurveParams::secp160k1(),
            CurveParams::secp160r1(),
            CurveParams::secp160r2(),
            CurveParams::p192(),
            CurveParams::p224(),
            CurveParams::p384(),
            CurveParams::p521(),
            CurveParams::secp192k1(),
            CurveParams::secp224k1(),
            CurveParams::gost_cryptopro_a(),
            CurveParams::gost_cryptopro_b(),
            CurveParams::gost_cryptopro_c(),
            CurveParams::gost_tc26_512_a(),
            CurveParams::gost_tc26_512_b(),
            CurveParams::gost_tc26_256_a(),
        ];
        for curve in &curves {
            assert!(
                curve.is_on_curve(&curve.generator()),
                "generator off curve for {}",
                curve.name,
            );
        }
    }

    /// **2 · G** computed via doubling agrees with **2 · G** via
    /// scalar-multiplication-by-two on every curve.  Catches mismatches
    /// between the explicit `Point::double` and the generic
    /// `Point::scalar_mul` paths.
    #[test]
    fn double_matches_scalar_mul_two_for_all_curves() {
        let curves = [
            CurveParams::brainpool_p256r1(),
            CurveParams::frp256v1(),
            CurveParams::secp160r1(),
            CurveParams::p384(),
            CurveParams::secp192k1(),
            CurveParams::gost_cryptopro_a(),
        ];
        for curve in &curves {
            let g = curve.generator();
            let a = curve.a_fe();
            let g2_double = g.double(&a);
            let g2_scalar = g.scalar_mul(&BigUint::from(2u32), &a);
            assert_eq!(g2_double, g2_scalar, "2·G mismatch on {}", curve.name,);
        }
    }

    /// **Order check on a small curve**: the cofactor-1 prime-order
    /// subgroup means `n · G = O` (infinity).  Doing this for every
    /// curve in the zoo is too expensive (P-521 alone is ≈521 ladder
    /// iterations of BigUint field ops, each iteration ~milliseconds),
    /// so we limit to brainpoolP192r1 which is fast.
    #[test]
    fn n_times_generator_is_infinity_for_legacy_low_security_curves() {
        for curve in [
            CurveParams::secp112r1(),
            CurveParams::secp112r2(),
            CurveParams::secp128r1(),
            CurveParams::secp128r2(),
            CurveParams::secp160k1(),
            CurveParams::secp160r1(),
            CurveParams::secp160r2(),
            CurveParams::p192(),
            CurveParams::brainpool_p192r1(),
        ] {
            let a = curve.a_fe();
            let ng = curve.generator().scalar_mul(&curve.n, &a);
            assert_eq!(ng, Point::Infinity, "n*G mismatch on {}", curve.name);
        }
    }

    #[test]
    fn legacy_curve_base_points_match_sec2_constants() {
        let cases = [
            (
                CurveParams::secp112r1(),
                "09487239995A5EE76B55F9C2F098",
                "A89CE5AF8724C0A23E0E0FF77500",
            ),
            (
                CurveParams::secp112r2(),
                "4BA30AB5E892B4E1649DD0928643",
                "ADCD46F5882E3747DEF36E956E97",
            ),
            (
                CurveParams::secp128r1(),
                "161FF7528B899B2D0C28607CA52C5B86",
                "CF5AC8395BAFEB13C02DA292DDED7A83",
            ),
            (
                CurveParams::secp128r2(),
                "7B6AA5D85E572983E6FB32A7CDEBC140",
                "27B6916A894D3AEE7106FE805FC34B44",
            ),
            (
                CurveParams::secp160k1(),
                "3B4C382CE37AA192A4019E763036F4F5DD4D7EBB",
                "938CF935318FDCED6BC28286531733C3F03C4FEE",
            ),
            (
                CurveParams::secp160r1(),
                "4A96B5688EF573284664698968C38BB913CBFC82",
                "23A628553168947D59DCC912042351377AC5FB32",
            ),
            (
                CurveParams::secp160r2(),
                "52DCB034293A117E1F4FF11B30F7199D3144CE6D",
                "FEAFFEF2E331F296E071FA0DF9982CFEA7D43F2E",
            ),
            (
                CurveParams::p192(),
                "188DA80EB03090F67CBF20EB43A18800F4FF0AFD82FF1012",
                "07192B95FFC8DA78631011ED6B24CDD573F977A11E794811",
            ),
        ];
        for (curve, gx, gy) in cases {
            assert_eq!(curve.gx, hexp(gx), "Gx mismatch on {}", curve.name);
            assert_eq!(curve.gy, hexp(gy), "Gy mismatch on {}", curve.name);
        }
    }

    #[test]
    fn legacy_curve_nominal_security_categories() {
        for curve in [CurveParams::secp112r1(), CurveParams::secp112r2()] {
            assert_eq!(curve.p.bits() / 2, 56, "{} should be ~56-bit", curve.name);
        }
        for curve in [CurveParams::secp128r1(), CurveParams::secp128r2()] {
            assert_eq!(curve.p.bits() / 2, 64, "{} should be ~64-bit", curve.name);
        }
        for curve in [
            CurveParams::secp160k1(),
            CurveParams::secp160r1(),
            CurveParams::secp160r2(),
        ] {
            assert_eq!(curve.n.bits() / 2, 80, "{} should be ~80-bit", curve.name);
        }
        assert_eq!(CurveParams::secp112r1().h, 1);
        assert_eq!(CurveParams::secp112r2().h, 4);
        assert_eq!(CurveParams::secp128r1().h, 1);
        assert_eq!(CurveParams::secp128r2().h, 4);
        assert_eq!(CurveParams::p192().n.bits() / 2, 96);
        assert_eq!(CurveParams::secp192r1().n, CurveParams::p192().n);
        assert_eq!(CurveParams::prime192v1().n, CurveParams::p192().n);
    }

    /// **Brainpool p256r1 — RFC 7027 §A.1 test vector** for 2·G.
    /// (k = 2: 2·G has coords given in RFC 7027 Appendix A.1.)
    #[test]
    fn brainpool_p256r1_two_times_g() {
        let curve = CurveParams::brainpool_p256r1();
        let a = curve.a_fe();
        let two_g = curve.generator().scalar_mul(&BigUint::from(2u32), &a);
        let (x, y) = match two_g {
            Point::Affine { x, y } => (x.value, y.value),
            Point::Infinity => panic!("2·G should not be infinity"),
        };
        // Computed independently using SageMath; deterministic.
        let want_x = BigUint::parse_bytes(
            b"743CF1B8B5CD4F2EB55F8AA369593AC436EF044166699E37D51A14C2CE13EA0E",
            16,
        )
        .unwrap();
        let want_y = BigUint::parse_bytes(
            b"36ED163337DEBA9C946FE0BB776529DA38DF059F69249406892ADA097EEB7CD4",
            16,
        )
        .unwrap();
        assert_eq!(x, want_x);
        assert_eq!(y, want_y);
    }

    /// **NIST P-256 reuses the existing constructor**: the new curves
    /// don't shadow it.  Sanity check.
    #[test]
    fn existing_curves_still_present() {
        assert_eq!(CurveParams::p256().name, "P-256");
        assert_eq!(CurveParams::secp256k1().name, "secp256k1");
        assert_eq!(CurveParams::sm2().name, "SM2");
    }

    // ── Quiet a never-used-zero warning when running with --no-default-features. ──
    #[allow(dead_code)]
    fn _quiet_zero(_: &BigUint) -> bool {
        BigUint::zero().is_zero()
    }
}
