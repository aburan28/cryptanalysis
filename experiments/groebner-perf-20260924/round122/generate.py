"""Cache the bounded-bitset eligibility of installed F4 reducers."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = "6d61834e95d1ff4673b1617ff0b9e2c3c0158aaf0a493b448877630719e75e6f"


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def fitcache_engine(source):
    assert hashlib.sha256(source.encode()).hexdigest() == ENGINE_SHA256
    source = once(source, "    bool bit_ready=false;\n",
                  "    bool bit_ready=false;\n"
                  "    size_t basis_wide_rows=0;\n")
    source = once(source, '''    bool fits_bitset(const Row& value,const std::vector<Row>& reducers) const {
        for (Mask term:value.terms) if (term & ~Mask(4095)) return false;
        for (const Row& row:reducers)
            for (Mask term:row.terms) if (term & ~Mask(4095)) return false;
        return true;
    }
''', '''    bool row_fits_bitset(const Row& row) const {
        for (Mask term:row.terms) if (term & ~Mask(4095)) return false;
        return true;
    }
    bool fits_bitset(const Row& value,const std::vector<Row>& reducers) const {
        if (!row_fits_bitset(value)) return false;
        if (&reducers==&basis) return basis_wide_rows==0;
        for (const Row& row:reducers)
            if (!row_fits_bitset(row)) return false;
        return true;
    }
''')
    source = once(source, '''        basis_leads.push_back(lm);
        basis.push_back(std::move(row));
''', '''        basis_leads.push_back(lm);
        if (!row_fits_bitset(row)) ++basis_wide_rows;
        basis.push_back(std::move(row));
''')
    source = once(source, '''                if (row.terms.empty()) {
                    basis.erase(basis.begin()+i);
                    basis_leads.erase(basis_leads.begin()+i);
                } else {
                    basis_leads[i]=lead(row.terms);
                    basis[i]=std::move(row);
                }
''', '''                if (row.terms.empty()) {
                    if (!row_fits_bitset(basis[i])) --basis_wide_rows;
                    basis.erase(basis.begin()+i);
                    basis_leads.erase(basis_leads.begin()+i);
                } else {
                    const bool old_wide=!row_fits_bitset(basis[i]);
                    const bool new_wide=!row_fits_bitset(row);
                    if (old_wide && !new_wide) --basis_wide_rows;
                    if (!old_wide && new_wide) ++basis_wide_rows;
                    basis_leads[i]=lead(row.terms);
                    basis[i]=std::move(row);
                }
''')
    return source
