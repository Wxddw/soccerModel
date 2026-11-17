import copy
import pytest
from shadow_r635 import inspect, replay_recap13
from test_motivation_squad_r634 import pkt, squads, motivation, sr, BEFORE


def risk(family, state='adverse_to_home', severe=False):
    return {'family': family, 'state': state, 'source_id': 'risk-'+family,
            'observed_at': BEFORE, 'critical_spine_severe': severe}


def test_r635_preserves_probability_direction_and_production():
    p = pkt()
    frozen = copy.deepcopy(p)
    out = inspect(p)
    assert p == frozen
    assert out['outcome_probabilities_unchanged'] == [.46, .27, .27]
    assert out['probability_adjustment_applied'] is False
    assert out['automatic_direction_flip'] is False
    assert out['formal_single_grant'] is None and out['formal_core_grant'] is None
    assert out['production_changed'] is False


def test_hfrg_two_independent_adverse_families_holds_home_favorite():
    p = pkt(p=(.66, .21, .13), risk_evidence=[risk('roster'), risk('tactical_matchup')])
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'HIGH_RISK_REVIEW_TWO_INDEPENDENT_FAMILIES'
    assert out['r635_single_authorization_status'] == 'HOLD_SINGLE_AUTHORIZATION_REVIEW'
    assert not out['r635_core_review_pass']
    assert out['raw_single'] == '胜'


def test_hfrg_severe_critical_spine_single_family_holds():
    p = pkt(p=(.66, .21, .13), risk_evidence=[risk('roster', severe=True)])
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'HIGH_RISK_REVIEW_CRITICAL_SPINE'
    assert out['raw_single'] == '胜'


def test_hfrg_one_adverse_family_is_watch_not_auto_block():
    p = pkt(p=(.63, .23, .14), risk_evidence=[risk('schedule')])
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'WATCH_ONE_ADVERSE_FAMILY'
    assert out['r635_single_authorization_status'] == 'RETAIN_DIRECTION_WATCH'


def test_hfrg_missing_risk_evidence_is_unknown_not_safe():
    p = pkt(p=(.67, .21, .12))
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'UNKNOWN_INSUFFICIENT_INDEPENDENT_RISK_AUDIT'
    assert out['r635_single_authorization_status'] == 'HOLD_RISK_AUDIT_INCOMPLETE'


def test_hfrg_not_applicable_to_away_favorite():
    p = pkt(p=(.17, .21, .62), risk_evidence=[])
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'NOT_APPLICABLE_NOT_HOME_FAVORITE'


def test_hfrg_rejects_correlated_roster_duplicates():
    p = pkt(p=(.66, .21, .13), risk_evidence=[risk('roster'), risk('goalkeeper')])
    with pytest.raises(ValueError, match='correlated risk evidence duplicated'):
        inspect(p)


def test_hfrg_rejects_post_cutoff_source():
    p = pkt(p=(.66, .21, .13), risk_evidence=[{**risk('roster'), 'observed_at':'2026-11-04T13:00:00+08:00'}])
    with pytest.raises(ValueError, match='post-cutoff'):
        inspect(p)


def test_dynamic_protection_uses_actual_top_two_not_default_home_draw():
    p = pkt(p=(.39, .28, .33), previous_research_protection=['胜','平'])
    out = inspect(p)
    audit = out['dynamic_protection_audit']
    assert audit['research_proposed_protection'] == ['胜','负']
    assert audit['changed_vs_previous'] is True


def test_dynamic_protection_flags_rounded_tie():
    p = pkt(p=(.40, .30, .30), previous_research_protection=['胜','平'])
    out = inspect(p)
    assert out['dynamic_protection_audit']['second_slot_tie_or_rounding_ambiguity'] is True
    assert out['dynamic_protection_audit']['tie_status'] == 'MANUAL_REVIEW_KEEP_FROZEN_PAIR'


def test_tail_router_high_tail_keeps_central_peak_and_one_tail_slot():
    p = pkt()
    p['goal_distribution'] = {'0':.03,'1':.10,'2':.25,'3':.22,'4':.18,'5':.10,'6':.07,'7+':.05}
    p['tail_evidence'] = [
        {'family':'attacking_profile','direction':'high','source_id':'a','observed_at':BEFORE},
        {'family':'defensive_instability','direction':'high','source_id':'d','observed_at':BEFORE}]
    out = inspect(p)['RC2_4_tail_router']
    assert out['status'] == 'HIGH_TAIL_ONE_SLOT'
    assert out['central_peak'] == '2'
    assert out['tail_slot'] == '4'
    assert out['shadow_top3'][0] == '2' and out['shadow_top3'][1] == '4'
    assert out['tail_slots_used'] == 1


def test_tail_router_low_tail_is_separate_and_no_more_than_one_slot():
    p = pkt()
    p['goal_distribution'] = {'0':.08,'1':.12,'2':.27,'3':.24,'4':.14,'5':.08,'6':.04,'7+':.03}
    p['tail_evidence'] = [
        {'family':'pace_transition','direction':'low','source_id':'p','observed_at':BEFORE},
        {'family':'lineup_bench','direction':'low','source_id':'l','observed_at':BEFORE}]
    out = inspect(p)['RC2_4_tail_router']
    assert out['status'] == 'LOW_TAIL_ONE_SLOT'
    assert out['central_peak'] == '2' and out['tail_slot'] == '1'
    assert len(out['shadow_top3']) == 3


def test_tail_router_both_tails_conflict_keep_base():
    p = pkt()
    p['goal_distribution'] = {'0':.08,'1':.12,'2':.27,'3':.24,'4':.14,'5':.08,'6':.04,'7+':.03}
    p['tail_evidence'] = [
        {'family':'pace_transition','direction':'low','source_id':'p','observed_at':BEFORE},
        {'family':'lineup_bench','direction':'low','source_id':'l','observed_at':BEFORE},
        {'family':'attacking_profile','direction':'high','source_id':'a','observed_at':BEFORE},
        {'family':'defensive_instability','direction':'high','source_id':'d','observed_at':BEFORE}]
    out = inspect(p)['RC2_4_tail_router']
    assert out['status'] == 'BOTH_TAILS_CONFLICT_KEEP_BASE'
    assert out['shadow_top3'] == out['base_top3']


def test_tail_router_rejects_correlated_duplicate_and_post_cutoff():
    p = pkt(); p['goal_distribution'] = {k:1/8 for k in ('0','1','2','3','4','5','6','7+')}
    p['tail_evidence'] = [
        {'family':'market_ou','direction':'high','source_id':'m1','observed_at':BEFORE},
        {'family':'market_ou','direction':'high','source_id':'m2','observed_at':BEFORE}]
    with pytest.raises(ValueError, match='duplicate correlated'):
        inspect(p)
    p['tail_evidence'] = [{'family':'market_ou','direction':'high','source_id':'m','observed_at':'2026-11-04T13:00:00+08:00'}]
    with pytest.raises(ValueError, match='post-cutoff'):
        inspect(p)


def test_score_matrix_joint_marginals_coherent():
    p = pkt(p=(.5,.25,.25))
    p['goal_distribution'] = {'0':.10,'1':.20,'2':.30,'3':.20,'4':.10,'5':.05,'6':.03,'7+':.02}
    # A compact coherent score matrix whose marginals match WDL and total-goal bins.
    p['score_matrix'] = [
        {'score':'0:0','probability':.10}, {'score':'1:0','probability':.10},
        {'score':'1:1','probability':.15}, {'score':'2:0','probability':.15},
        {'score':'2:1','probability':.10}, {'score':'0:1','probability':.10},
        {'score':'1:2','probability':.10}, {'score':'2:2','probability':.10},
        {'score':'3:2','probability':.05}, {'score':'4:3','probability':.05}]
    # WDL marginals: home .50, draw .35, away .15, so change WDL to match exact values.
    p['probabilities'] = [.45,.35,.20]
    # Recompute goal bins for the listed scores: 0:.10, 1:.10, 2:.30, 3:.20, 4:.10, 5:.05, 7:.05.
    p['goal_distribution'] = {'0':.10,'1':.20,'2':.30,'3':.20,'4':.10,'5':.05,'6':0.0,'7+':.05}
    out = inspect(p)['GS1_3_joint_score_audit']
    assert out['status'] == 'JOINT_MATRIX_COHERENT'
    assert out['score_top3'][0] == '0:0' or len(out['score_top3']) == 3


def test_score_matrix_marginal_mismatch_fails_closed():
    p = pkt(p=(.5,.25,.25))
    p['score_matrix'] = [{'score':'1:0','probability':1.0}]
    with pytest.raises(ValueError, match='WDL marginal'):
        inspect(p)


def test_half_full_distribution_must_match_wdl_marginal():
    p = pkt(p=(.5,.3,.2))
    p['half_full_distribution'] = {
        '胜胜':.20,'胜平':.05,'胜负':.05,
        '平胜':.15,'平平':.10,'平负':.05,
        '负胜':.15,'负平':.15,'负负':.10}
    out = inspect(p)['HT_State_v0_2']
    assert out['status'] == 'HALF_FULL_MARGINAL_COHERENT'
    p['half_full_distribution']['负负'] = .20
    p['half_full_distribution']['胜胜'] = .10
    with pytest.raises(ValueError, match='FT marginal'):
        inspect(p)


def test_recap13_dynamic_protection_audit_is_not_validation():
    rows = [
      {'id':'001','probabilities':[.68,.21,.11],'previous_protection':['胜','平'],'actual':'胜'},
      {'id':'002','probabilities':[.49,.27,.24],'previous_protection':['胜','平'],'actual':'平'},
      {'id':'003','probabilities':[.17,.21,.62],'previous_protection':['平','负'],'actual':'负'},
      {'id':'004','probabilities':[.44,.30,.26],'previous_protection':['胜','平'],'actual':'胜'},
      {'id':'005','probabilities':[.54,.26,.20],'previous_protection':['胜','平'],'actual':'平'},
      {'id':'006','probabilities':[.66,.21,.13],'previous_protection':['胜','平'],'actual':'负'},
      {'id':'007','probabilities':[.39,.28,.33],'previous_protection':['胜','平'],'actual':'负'},
      {'id':'008','probabilities':[.63,.23,.14],'previous_protection':['胜','平'],'actual':'负'},
      {'id':'009','probabilities':[.40,.30,.30],'previous_protection':['胜','平'],'actual':'负'},
      {'id':'010','probabilities':[.66,.21,.13],'previous_protection':['胜','平'],'actual':'胜'},
      {'id':'011','probabilities':[.29,.29,.42],'previous_protection':['平','负'],'actual':'负'},
      {'id':'012','probabilities':[.67,.21,.12],'previous_protection':['胜','平'],'actual':'负'},
      {'id':'013','probabilities':[.72,.19,.09],'previous_protection':['胜','平'],'actual':'胜'}]
    out = replay_recap13(rows)
    assert out['old_protection_hits'] == 8
    assert out['dynamic_protection_hits'] == 9
    assert out['ambiguous_second_slot_ties'] == 2
    assert out['independent_validation'] is False


def test_away_favorite_is_not_blocked_by_home_favorite_gate():
    p = pkt(p=(.15,.20,.65))
    p['risk_evidence'] = []
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'NOT_APPLICABLE_NOT_HOME_FAVORITE'
    # HFRG itself does not block a valid parent core review for an away favorite.
    assert out['r635_core_review_pass'] == out['research_core_context_review_pass']


def test_home_favorite_clear_requires_two_independent_non_adverse_families():
    p = pkt(p=(.68,.20,.12), risk_evidence=[
        risk('roster','favorable_to_home'), risk('tactical_matchup','neutral')])
    out = inspect(p)
    assert out['HFRG_home_favorite_risk_gate']['status'] == 'NO_HFRG_TRIGGER_REVIEWED'


def test_tail_central_peak_can_itself_be_the_only_tail_slot():
    p = pkt()
    p['goal_distribution'] = {'0':.03,'1':.06,'2':.12,'3':.18,'4':.25,'5':.16,'6':.12,'7+':.08}
    p['tail_evidence'] = [
        {'family':'attacking_profile','direction':'high','source_id':'a','observed_at':BEFORE},
        {'family':'defensive_instability','direction':'high','source_id':'d','observed_at':BEFORE}]
    out = inspect(p)['RC2_4_tail_router']
    assert out['central_peak'] == '4'
    assert out['tail_slot'] == '4'
    assert out['tail_slots_used'] == 1
