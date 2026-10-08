"""Reorder unchanged independent checker obligations; never omit one on acceptance."""
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent

def source():
    path=HERE.parent/'round11/native_checker.cpp'
    text=path.read_text()
    expected='eaf4b4fd634281472012c4f4617590afb504c69f538789d5059bd0a580131dff'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    def change(old,new):
        nonlocal text
        assert text.count(old)==1,old[:100]
        text=text.replace(old,new)
    change('void finish_phase(){record_phase();phase=Clock::now();++phase_index;}',
           'void select_phase(unsigned next){record_phase();phase=Clock::now();phase_index=next;}')
    change('void verify(const PackedInput& input,const ProofView& proof)',
           'void verify(const PackedInput& input,const ProofView& proof,uint32_t schedule)')
    start=text.index('        finish_phase();\n        charge(proof.nodes);')
    end=text.index('\n    }\n};',start)
    body=text[start:end]
    parts=body.split('        finish_phase();')
    assert len(parts)==6 and not parts[0].strip() and not parts[-1].strip()
    derivation,membership,reducedness,completion=parts[1:5]
    declaration='        std::vector<uint64_t> leads;leads.reserve(basis.size());\n'
    assert membership.count(declaration)==1
    membership=membership.replace(declaration,'        leads.reserve(basis.size());\n')
    value_decl='charge(proof.nodes);std::vector<Polynomial> values;values.reserve(proof.nodes);'
    assert derivation.count(value_decl)==1
    derivation=derivation.replace(value_decl,'charge(proof.nodes);values.reserve(proof.nodes);')
    replacement='\n        std::vector<uint64_t> leads;\n        std::vector<Polynomial> values;\n'
    for label,code in [('derivation',derivation),('membership',membership),('reducedness',reducedness),('completion',completion)]:
        replacement+='        auto '+label+' = [&]() {'+code+'\n        };\n'
    replacement+='''        if (schedule == 0) {
            select_phase(1); derivation();
            select_phase(2); membership();
            select_phase(3); reducedness();
            select_phase(4); completion();
        } else {
            select_phase(2); membership();
            select_phase(3); reducedness();
            select_phase(4); completion();
            select_phase(1); derivation();
        }
        select_phase(5);'''
    text=text[:start]+replacement+text[end:]
    change('int check_packed(const PackedInput* input,const ProofView* proof,uint64_t max_work,\n                 uint64_t max_retained_terms,CheckStats* stats)',
           'int check_packed_ordered(const PackedInput* input,const ProofView* proof,uint64_t max_work,\n                 uint64_t max_retained_terms,uint32_t schedule,CheckStats* stats)')
    change('if(!input||!proof||input->nvars<1', 'if(schedule>1||!input||!proof||input->nvars<1')
    change('checker.verify(*input,*proof);', 'checker.verify(*input,*proof,schedule);')
    assert 'finish_phase' not in text
    return text

if __name__=='__main__': print(source())
