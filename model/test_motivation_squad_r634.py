import copy
import json
import math
from pathlib import Path
import pytest
from motivation_squad_r634 import inspect, effective_squad_strength, motivation_stakes, replay_development
from selection_efficiency_r633 import recommend

CUT='2026-11-04T12:00:00+08:00'
KICK='2026-11-04T21:00:00+08:00'
BEFORE='2026-11-04T09:00:00+08:00'


def sr(suffix,basis=None,**kwargs):
    return {'source_id':'s-'+suffix,'observed_at':BEFORE,**({'basis':basis} if basis is not None else {}),**kwargs}


def players(side,keeper_change=0,change=0):
    # Four defenders, three mids, three attackers, one keeper. A replacement plays
    # only when the baseline keeper loses its 90 projected minutes.
    core=[('GK','goalkeeper',80),('CB1','center_back',70),('CB2','center_back',70),
          ('FB1','fullback',70),('FB2','fullback',70),('DM','defensive_midfielder',70),
          ('CM','central_midfielder',70),('AM','attacking_midfielder',70),
          ('RW','winger',70),('ST','striker',70),('LW','winger',70)]
    ps=[]
    for i,(pid,role,rating) in enumerate(core):
        expected=90
        if i==0 and keeper_change:expected=0
        if i==1 and change: expected=0
        ps.append({'id':side+pid, 'role':role,'rating_0_100':rating,
                   'expected_minutes':expected,'reference_minutes':90,
                   'availability':'available' if expected else 'unavailable'})
    if keeper_change:
        ps.append({'id':side+'BackupGK','role':'goalkeeper','rating_0_100':80+keeper_change,
                   'expected_minutes':90,'reference_minutes':0,'availability':'available'})
    if change:
        ps.append({'id':side+'BackupCB','role':'center_back','rating_0_100':70+change,
                   'expected_minutes':90,'reference_minutes':0,'availability':'available'})
    return ps


def squads(home_keeper_change=0,home_cb_change=0,away_keeper_change=0, status='confirmed'):
    return {
      side:{'lineup_status':status,
            'minutes_source':sr(side+'-XI',method='confirmed_starters_projected_minutes' if status=='confirmed' else 'projected_starters_projected_minutes'),
            'rating_model_source':sr(side+'-rating',method='independent_prior_player_ratings',scale_id='calibrated_shared_pool',trained_until='2026-11-03T12:00:00+08:00'),
            'players':players(side,keeper_change=(home_keeper_change if side=='home' else away_keeper_change),change=(home_cb_change if side=='home' else 0))}
        for side in ('home','away')}


def motivation(home_urg='high',away_urg='low',home_must=True,away_must=False):
    return {side:{'competition_context':'league','stakes_type': 'relegation' if side=='home' else 'routine',
                  'urgency':home_urg if side=='home' else away_urg,
                  'win_mathematically_necessary':home_must if side=='home' else away_must,
                  'basis_source':sr(side+'-league',basis='official_table_and_rules'),
                  'next_fixture_days':4, 'fixture_source':sr(side+'-fixture',basis='official_schedule')}
           for side in ('home','away')}


def pkt(p=(.46,.27,.27), **kw):
    q={'id':'010','cutoff':CUT,'kickoff':KICK,'ordinary_sale':True,
       'probabilities':list(p),'evidence':[
         {'family':'official_lineup','source_id':'source-XI','observed_at':BEFORE,'state':'favorable'},
         {'family':'market_price','source_id':'price','observed_at':BEFORE,'state':'neutral'}],
       'squads':squads(), 'motivation':motivation()}
    q.update(kw)
    return q


def test_01_direction_and_probability_unchanged():
    p=pkt(); frozen=copy.deepcopy(p);res=inspect(p)
    assert p==frozen and res['raw_single']=='胜'
    assert res['unmodified_probabilities']==recommend(p)['outcome_probabilities_unchanged']
    assert not res['probability_adjustment_applied'] and res['formal_single_grant'] is None


def test_02_both_complete_and_motivation_is_not_win_probability():
    out=inspect(pkt())
    assert out['effective_squad_ESR']['status']=='CONFIRMED_BOTH'
    assert out['objective_stakes_MSI']['status']=='VERIFIED_BOTH'
    assert out['objective_stakes_MSI']['win_necessity_not_win_probability'] is True
    assert out['raw_direction_stakes_context']=='RAW_DIRECTION_HIGH_STAKES'


def test_03_keeper_replacement_identifies_understrength():
    r=inspect(pkt(squads=squads(home_keeper_change=-30)))
    assert r['effective_squad_ESR']['sides']['home']['role_contributions']['goalkeeper']<0
    assert r['effective_squad_ESR']['relative_shift']<0
    assert r['raw_direction_capacity_alignment']=='ADVERSE_TO_RAW_DIRECTION'
    assert r['intent_capacity_conflict'] and not r['research_recovery_context_review_pass']


def test_04_good_quality_replacement_small_effect():
    r=inspect(pkt(squads=squads(home_keeper_change=-1)))
    assert math.isclose(r['effective_squad_ESR']['relative_shift'],-1/11,abs_tol=1e-12)
    assert r['raw_direction_capacity_alignment']=='NEUTRAL_NEAR_BASELINE'


def test_05_away_with_weakened_keeper_helps_home_relative_swing():
    r=inspect(pkt(squads=squads(away_keeper_change=-33)))
    assert r['effective_squad_ESR']['relative_shift']>=2
    assert r['raw_direction_capacity_alignment']=='SUPPORTS_RAW_DIRECTION'


def test_06_away_single_direction_sign_reversed():
    r=inspect(pkt(p=(.27,.27,.46),squads=squads(away_keeper_change=-33)))
    assert r['raw_single']=='负'
    assert r['raw_direction_capacity_alignment']=='ADVERSE_TO_RAW_DIRECTION'


def test_07_draw_not_inferred_from_motivation_parity():
    r=inspect(pkt(p=(.30,.41,.29)))
    assert r['raw_single']=='平' and 'DRAW_NOT_A_FUNCTION_OF_MOTIVATION_PARITY' in r['audit_flags']


def test_08_no_data_unknown_no_false_low_risk():
    p=pkt();p.pop('squads');p.pop('motivation');res=inspect(p)
    assert res['raw_single']=='胜'
    assert 'MISSING_EFFECTIVE_SQUAD_STRENGTH' in res['audit_flags']
    assert not res['research_recovery_context_review_pass']


def test_09_projected_lineup_does_not_pass_confirmed_core():
    r=inspect(pkt(p=(.74,.15,.11),squads=squads(status='projected'), evidence=[
        {'family':'official_lineup','source_id':'source-XI','observed_at':BEFORE,'state':'favorable'},
        {'family':'market_price','source_id':'price','observed_at':BEFORE,'state':'favorable'}]))
    assert not r['research_core_context_review_pass']
    assert 'LINEUP_PROJECTED_NOT_CONFIRMED' in r['audit_flags']


def test_10_core_no_actual_grant_even_if_complete():
    r=inspect(pkt(p=(.74,.15,.11),evidence=[
        {'family':'official_lineup','source_id':'source-XI','observed_at':BEFORE,'state':'favorable'},
        {'family':'market_price','source_id':'price','observed_at':BEFORE,'state':'favorable'}]))
    assert r['research_core_context_review_pass']
    assert r['formal_core_grant'] is None


def test_11_no_subjective_coach_claim_can_be_math_must_win():
    p=pkt();p['motivation']['home']['basis_source']['basis']='official_team_statement'
    with pytest.raises(ValueError,match='must-win'):inspect(p)


def test_12_no_postcutoff_motivation_source():
    p=pkt();p['motivation']['home']['basis_source']['observed_at']='2026-11-04T13:00:00+08:00'
    with pytest.raises(ValueError,match='post-cutoff'):inspect(p)


def test_13_no_postcutoff_rating_source():
    p=pkt();p['squads']['home']['rating_model_source']['observed_at']='2026-11-04T13:00:00+08:00'
    with pytest.raises(ValueError,match='post-cutoff'):inspect(p)


def test_14_no_trained_on_current_match_outcome():
    p=pkt();p['squads']['home']['rating_model_source']['trained_until']=CUT
    with pytest.raises(ValueError,match='trained before cutoff'):inspect(p)


def test_15_no_missing_unbalanced_990_minutes():
    p=pkt();p['squads']['home']['players'][1]['expected_minutes']=0
    with pytest.raises(ValueError,match='990'):inspect(p)


def test_16_no_unavailable_player_with_positive_minutes():
    p=pkt();p['squads']['home']['players'][1]['availability']='unavailable'
    with pytest.raises(ValueError,match='unavailable player'):inspect(p)


def test_17_one_source_both_teams_is_valid_not_two_votes():
    p=pkt();p['motivation']['away']['basis_source']['source_id']=p['motivation']['home']['basis_source']['source_id']
    r=inspect(p)
    assert r['objective_stakes_MSI']['status']=='VERIFIED_BOTH'
    assert r['objective_stakes_MSI']['shared_source_between_teams']


def test_18_no_red_card_in_prematch():
    p=pkt();p['motivation']['home']['red_card']=1
    with pytest.raises(ValueError,match='post-match'):inspect(p)


def test_19_parent_protection_hardlock():
    p=pkt(frozen_single='胜',frozen_protection=['平','负'])
    with pytest.raises(ValueError,match='protection mismatch'):inspect(p)


def test_20_any_wrong_squad_rating_schema_rejected():
    p=pkt();p['squads']['home']['players'][0]['rating_0_100']=101
    with pytest.raises(ValueError,match='0-100'):inspect(p)


def test_21_dont_fake_future_lineup_as_confirmed():
    p=pkt();p['squads']['home']['minutes_source']['method']='projected_starters_projected_minutes'
    with pytest.raises(ValueError,match='confirmed lineup status'):inspect(p)


def test_22_stakes_opponent_high_not_favorable_by_itself():
    m=motivation(home_urg='low',away_urg='high',home_must=False,away_must=True)
    m['home']['stakes_type']='routine';m['away']['stakes_type']='title'
    r=inspect(pkt(motivation=m))
    assert r['raw_direction_stakes_context']=='OPPONENT_HIGH_STAKES'
    assert not r['research_recovery_context_review_pass']


def test_23_replay_41_remains_unverified_without_stakes_and_xi():
    rows=json.loads((Path(__file__).parent/'paired_input_DEV_ONLY_41.json').read_text())
    result=replay_development(rows)
    assert result['n']==41 and result['missing_roster_n']==41 and result['missing_stakes_n']==41
    assert result['context_verified_recoveries']==0 and result['context_verified_cores']==0
    assert result['formal_grant'] is None


def test_24_objective_must_win_both_not_asymmetric():
    m=motivation(home_urg='high',away_urg='high',home_must=True,away_must=True)
    m['away']['stakes_type']='title'
    r=inspect(pkt(motivation=m))
    assert r['objective_stakes_MSI']['asymmetry']=='BOTH_HIGH'
    assert r['raw_direction_stakes_context']=='NO_SIMPLE_DIRECTIONAL_MOTIVATION'


def test_25_rest_and_lineup_do_not_create_extra_votes():
    r=inspect(pkt(squads=squads(home_cb_change=-20)))
    assert r['formal_single_grant'] is None
    assert 'Rest/fixture congestion and a rotation-triggered lineup change are causally correlated; do not double count.' in r['notes']


def test_26_common_rating_scale_required():
    p=pkt();p['squads']['away']['rating_model_source']['scale_id']='different_league_raw_ratings'
    with pytest.raises(ValueError,match='same calibrated player rating scale'):inspect(p)

def test_27_absolute_available_strength_and_normal_shift_are_separate():
    r=inspect(pkt(squads=squads(home_keeper_change=-25)))
    s=r['effective_squad_ESR']
    assert 'effective_quality_home_minus_away' in s
    assert 'reference_quality_home_minus_away' in s
    assert s['effective_quality_home_minus_away'] < s['reference_quality_home_minus_away']

def test_28_goalkeeper_drop_and_short_schedule_flags():
    p=pkt(squads=squads(home_keeper_change=-25));p['motivation']['home']['next_fixture_days']=2
    r=inspect(p)
    assert 'HOME_GOALKEEPER_REPLACEMENT_QUALITY_DROP_REVIEW' in r['audit_flags']
    assert 'HOME_SHORT_TURNAROUND_ROTATION_AND_MOTIVATION_TRADEOFF' in r['audit_flags']
    assert r['formal_core_grant'] is None
