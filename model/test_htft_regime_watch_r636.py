import copy
import pytest
from htft_regime_watch_r636 import audit, cohort, PATHS
from joint_tail_calibration_shadow_r636 import grid,aggregates
from test_joint_tail_calibration_shadow_r636 import Q

HTFT = {k:0. for k in PATHS}
# Fill entirely plausible nine-state marginals from Q (not a clinical prediction)
FT=aggregates(grid(Q))['wdl']
for x in ('胜','平','负'):
    for y in ('胜','平','负'):
        HTFT[x+y]=FT[y]/3

def packet():
    return {'match_id':'future-HT','source_id':'frozen',
        'observed_at':'2026-02-03T12:00:00+08:00',
        'cutoff':'2026-02-03T13:00:00+08:00',
        'kickoff':'2026-02-03T19:00:00+08:00',
        'score_matrix':copy.deepcopy(Q),'htft_probabilities':copy.deepcopy(HTFT),
        'published_htft_top2':['胜胜','平胜'], 'snapshot_decimal_places':None}

def test_htft_frozen_marginal_and_special_paths():
    x=audit(packet())
    assert x['formal_grant'] is None
    assert x['special_family_probability']['halftime_lead_lost']>0
    assert cohort([x])['expected_htft_top2_hits']==pytest.approx(x['top2_probability_mass'])

def test_htft_rejects_postmatch_field_and_marginal_mismatch():
    x=packet();x['postmatch_score']='1:1'
    with pytest.raises(ValueError):audit(x)
    x=packet();x['htft_probabilities']['负负']+=.05
    with pytest.raises(ValueError):audit(x)

def test_htft_rounded_input_contract():
    x=packet();x['htft_probabilities']={k:round(v,5) for k,v in HTFT.items()}
    x['snapshot_decimal_places']=5
    assert audit(x)['rounded_input_tolerance']>1e-5
    x['snapshot_decimal_places']=None
    with pytest.raises(ValueError):audit(x)

def test_htft_rejects_wrong_rank_and_duplicate_cohort():
    x=packet();x['published_htft_top2']=['胜胜','负胜']
    with pytest.raises(ValueError):audit(x)
    y=audit(packet())
    with pytest.raises(ValueError):cohort([y,y])
