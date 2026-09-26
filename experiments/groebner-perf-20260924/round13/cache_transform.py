"""Apply explicit, checked basis-leading-term cache edits to the frozen Engine."""


def cached_engine(source):
    def change(old, new, count=1):
        nonlocal source
        if source.count(old) != count:
            raise RuntimeError('basis cache insertion point changed: ' + old)
        source = source.replace(old, new)

    change('    std::vector<Row> basis;',
           '    std::vector<Row> basis;\n    std::vector<Mask> basis_leads;')
    change('for (const auto& g:reducers) leads.push_back(lead(g.terms));',
           'if (&reducers==&basis) leads=basis_leads;\n'
           '        else for (const auto& g:reducers) leads.push_back(lead(g.terms));', 2)
    change('Mask other=lead(basis[i].terms);', 'Mask other=basis_leads[i];')
    change('        basis.push_back(std::move(row));',
           '        basis_leads.push_back(lm);\n        basis.push_back(std::move(row));')
    change('for (const auto& row:basis) leads.push_back(lead(row.terms));',
           'leads=basis_leads;')
    change('Mask a=lead(basis[p.i].terms),b=lead(basis[p.j].terms),common=a|b;',
           'Mask a=basis_leads[p.i],b=basis_leads[p.j],common=a|b;')
    change('if (row.terms.empty()) basis.erase(basis.begin()+i);\n'
           '                else basis[i]=std::move(row);',
           'if (row.terms.empty()) {\n'
           '                    basis.erase(basis.begin()+i);\n'
           '                    basis_leads.erase(basis_leads.begin()+i);\n'
           '                } else {\n'
           '                    basis_leads[i]=lead(row.terms);\n'
           '                    basis[i]=std::move(row);\n'
           '                }')
    finish='        std::sort(basis.begin(),basis.end(),[](const Row& a,const Row& b){return less_monomial(lead(b.terms),lead(a.terms));});'
    change(finish, finish+'\n        basis_leads.clear();\n'
           '        for (const auto& row:basis) basis_leads.push_back(lead(row.terms));')
    return source
