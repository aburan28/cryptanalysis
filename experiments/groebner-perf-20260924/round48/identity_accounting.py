"""Independent operation accounting for complete multiplier identity checks."""
from math import comb

IDENTITY_MODES = {'dense': 0, 'reduce': 1, 'packed': 2, 'local': 3,
                  'grouped': 4, 'grouped_local': 5, 'factored': 6, 'factored_local': 7}
CONTROL_VARIANTS = tuple(('full', mode) for mode in IDENTITY_MODES)
QUERY_VARIANTS = tuple((transform, mode) for transform in ('full', 'tile16')
                       for mode in IDENTITY_MODES)


def per_record(y, equations, mode):
    if isinstance(mode,str):mode=IDENTITY_MODES[mode]
    assert mode in IDENTITY_MODES.values()
    limbs=(equations+63)//64
    features=1+y+comb(y,2)
    groups=features+comb(y,3)
    dense=(y+1)*features*limbs
    ands=(1+2*y+3*comb(y,2)+3*comb(y,3))*limbs if mode>=6 else dense
    copied=mode in (3,5,7)
    return {'ands':ands,'accumulator_xors':ands,
            'witness_xors':(y+2*comb(y,2))*limbs if mode>=6 else 0,
            'identity_xors':(y+1)*features if mode<4 else 0,
            'parities':groups if mode>=4 else dense,
            'table_loads':features*limbs if copied else ands,
            'cached_loads':ands if copied else 0,
            'copy_words':features*limbs if copied else 0}


def reconcile_identity(check,x,y,e,*,audit=False):
    assert check['verified']
    i,s,n=check['identity_check_stats'],check['symmetry_check_stats'],check['stats']
    mode=i['mode'];one=per_record(y,e,mode);limbs=(e+63)//64
    assert n['multiplier_words']%((y+1)*limbs)==0
    records=n['multiplier_words']//((y+1)*limbs)
    assert i['attempted_records']==records
    assert i['reused_records']==s['multiplier_aliases']
    for key,value in one.items():assert i[key]==records*value,(key,i[key],records*value)
    assert n['multiplier_parities']==i['parities']
    assert s['avoided_multiplier_parities']==i['reused_records']*one['parities']
    dense=per_record(y,e,0)['parities']
    assert i['dense_equivalent_parities']==records*dense
    assert 0<i['layout_bytes']<=16384
    assert i['cache_stack_bytes']==(896 if records and mode in (3,5,7) else 0)
    assert i['identity_stack_bytes']==((0 if mode>=4 else 128 if mode==2 else 1024) if records else 0)
    assert i['audit_records']==(records if audit else 0)
    assert i['audit_coefficients']==i['audit_records']*(1<<y)
    assert i['audit_parities']==i['audit_records']*(dense+one['parities'])


def equivalent_stats(check):
    values=dict(check['stats'])
    values['multiplier_parities']=check['identity_check_stats']['dense_equivalent_parities']
    return values
