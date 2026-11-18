import copy
import math
import pytest
from selection_efficiency_r633 import recommend, paired_audit
from build_development_archive import extract


def record(p=None, **kwargs):
    x = {'id':'001', 'date':'10-22',
         'cutoff':'2026-10-22T12:00:00+08:00',
         'kickoff':'2026-10-22T19:30:00+08:00',
         'probabilities': p or [.44,.30,.26],
         'ordinary_sale':True,'evidence': []}
    x.update(kwargs)
    return x


def ev(group, state='favorable', observed='2026-10-22T11:10:00+08:00'):
    return {'family':group,'state':state,'source_id':'source-'+group,'observed_at':observed}


def test_unique_direction_even_when_blocked():
    r = recommend(record([.36,.35,.29])); assert r['raw_single']=='胜'
    assert r['status']=='BLOCK_LT40' and not r['shadow_potential_eligible']
    assert r['formal_single_grant'] is None


def test_recovery_is_review_not_actual_grant():
    r = recommend(record([.44,.30,.26]));assert r['raw_single']=='胜'
    assert r['shadow_potential_eligible'] and not r['reference_proxy_eligible']
    assert not r['shadow_recovery_evidence_verified']
    assert r['formal_single_grant'] is None and not r['production_changed']


def test_recovery_below_margin_not_selected():
    r=recommend(record([.44,.35,.21]));assert not r['shadow_potential_eligible']


def test_recovery_gap_boundary_equality():
    r=recommend(record([.42,.30,.28]));assert r['shadow_potential_eligible']


def test_no_sale_no_grant():
    r=recommend(record(ordinary_sale=False));assert r['status']=='UNAVAILABLE_ORDINARY'
    assert not r['shadow_potential_eligible']


def test_two_genuinely_independent_favorable_allow_core_review():
    r=recommend(record([.73,.16,.11], evidence=[ev('official_lineup'),ev('market_price')]))
    assert r['shadow_core_structural_potential'] and r['shadow_core_evidence_review_pass']
    assert r['formal_core_grant'] is None


def test_one_family_no_core_grant():
    r=recommend(record([.73,.16,.11], evidence=[ev('market_price')]))
    assert r['shadow_core_structural_potential'] and not r['shadow_core_evidence_review_pass']


def test_adverse_two_independent_reject_recovery():
    r=recommend(record(evidence=[ev('market_price','adverse'),ev('official_lineup','adverse')]))
    assert not r['shadow_potential_eligible']


def test_independent_positive_evidence_verifies_recovery_but_no_formal_grant():
    r=recommend(record(evidence=[ev('official_lineup'), ev('schedule')]))
    assert r['shadow_recovery_evidence_verified']
    assert r['formal_single_grant'] is None


def test_correlated_market_price_buy_in_do_not_double_count():
    x=record([.73,.16,.11],evidence=[ev('market_price'),ev('market_funds')])
    with pytest.raises(ValueError,match='correlated'):recommend(x)


def test_lineup_and_team_news_do_not_double_count():
    x=record([.73,.16,.11],evidence=[ev('official_lineup'),ev('team_news')])
    with pytest.raises(ValueError,match='correlated'):recommend(x)


def test_postcutoff_data_rejected():
    x=record(evidence=[ev('market_price',observed='2026-10-22T12:05:00+08:00')])
    with pytest.raises(ValueError,match='post-cutoff'):recommend(x)


def test_inmatch_data_cannot_influence_prediction():
    x=record();x['market']={'inplay_event':{'red_card':True}}
    with pytest.raises(ValueError,match='post-match'):recommend(x)


def test_frozen_protection_containment_fail_closed():
    with pytest.raises(ValueError,match='protection mismatch'):
        recommend(record(frozen_single='胜',frozen_protection=['平','负']))


def test_frozen_direction_conflict_no_auto_flip():
    r=recommend(record(frozen_single='负',frozen_protection=['平','负']))
    assert r['direction_conflict'] and 'CONFLICT' in r['status']
    assert r['frozen_single_unchanged']=='负' and not r['shadow_potential_eligible']


def test_valid_existing_protection_unchanged():
    r=recommend(record(frozen_single='胜',frozen_protection=['胜','负']))
    assert r['frozen_protection_unchanged']==['胜','负']
    assert r['research_proposed_protection']==['胜','平']


def test_probabilities_unmodified_and_score_delta_zero():
    x=record([.44,.30,.26]); xcopy=copy.deepcopy(x)
    r=recommend(x); assert x==xcopy
    assert all(math.isclose(a,b) for a,b in zip(x['probabilities'],r['outcome_probabilities_unchanged']))
    d=paired_audit([{'prematch':x,'actual_score':[1,0],'split':'development'}])
    assert d['mean_brier_reference']==d['mean_brier_shadow']
    assert d['mean_logloss_reference']==d['mean_logloss_shadow']


def test_no_outcome_results_in_prematch_allowed():
    with pytest.raises(ValueError,match='post-match'):
        recommend(record(actual_score=[2,0]))


def test_nondevelopment_mislabeled_holdout_disallowed():
    with pytest.raises(ValueError,match='development only'):
        paired_audit([{'prematch':record(), 'actual_score':[1,0],'split':'holdout'}])


def test_bad_probabilities_rejected():
    with pytest.raises(ValueError):recommend(record([.5,.5,.4]))
    with pytest.raises(ValueError):recommend(record([.5,.5,float('nan')]))


def test_cutoff_time_zone_and_kickoff_checked():
    with pytest.raises(ValueError,match='timezone'):recommend(record(cutoff='2026-10-22T12:00:00'))
    with pytest.raises(ValueError,match='cutoff must precede'):recommend(record(kickoff='2026-10-22T11:59:59+08:00'))


def test_archive_41_consistent_development_only():
    rows, provenance=extract(); audit=paired_audit(rows)
    assert len(rows)==41 and provenance['sale_n']==37
    assert audit['reference_observation_proxy']['selected']==25
    assert audit['shadow_probability_only_potential']['selected']==29
    assert audit['recovery_n']==4 and audit['recovery_hits']==3 and audit['recovery_misses']==1
    assert audit['formal_grant_count'] is None and audit['independent_forward_improvement'] is None
    assert not any(r['shadow_recovery_evidence_verified'] for r in audit['rows'])


def test_two_neutral_evidence_not_a_supportive_recovery_confirmation():
    r=recommend(record(evidence=[ev('official_lineup','neutral'),ev('schedule','neutral')]))
    assert r['shadow_potential_eligible']
    assert not r['shadow_recovery_evidence_verified']
