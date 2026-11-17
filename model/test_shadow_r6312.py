"""Joint-grid conservation, Chinese JC integer handicaps and forward safety."""
import copy
import math
from datetime import datetime, timedelta, timezone
import pytest

from joint_bridge_r6312 import aggregate, jc_label, goal_bucket
from shadow_r6312 import inspect, VERSION
from forward_validation_r6312 import freeze, evaluate, summary
from test_shadow_r639 import jc_pkt
from test_shadow_r637 import coherent_packet
from test_shadow_r6311 import future_packet
from test_motivation_squad_r634 import pkt


def rows():
    return copy.deepcopy(coherent_packet()['score_matrix'])


def make_from_score_pairs(pairs, line=None, frozen_pick='让负'):
    packet=pkt()
    packet['score_matrix']=[{'score':s,'probability':p} for s,p in pairs]
    wp=[0.,0.,0.];gd={str(k):0. for k in range(7)};gd['7+']=0.
    for s,p in pairs:
        h,a=map(int,s.split(':'));wp[0 if h>a else 1 if h==a else 2]+=p
        gd[str(h+a) if h+a<=6 else '7+']+=p
    packet['probabilities']=wp
    packet['goal_distribution']=gd
    if line is not None:
        packet.update(official_handicap_line=line,
                      official_handicap_line_source={'basis':'official_jc_handicap',
                          'source_id':'official-canned-fixture','observed_at':'2026-11-04T09:00:00+08:00'},
                      frozen_handicap_pick=frozen_pick)
    return packet


def simple():
    return [('1:0',.18),('2:1',.17),('1:1',.15),('2:0',.12),
            ('2:2',.12),('0:1',.10),('0:0',.08),('0:2',.08)]


def test_base_215_inherited_and_shadow_only():
    p=jc_pkt(-1);before=copy.deepcopy(p)
    result=inspect(p);z=result['S4_GS_RC_unified_probability_bridge_v312']
    assert result['version']==VERSION
    assert p==before
    assert result['outcome_probabilities_unchanged']==[.5,.3,.2]
    assert z['raw_score_top3']==['2:0','2:2','1:0']
    assert all(result[k] is None for k in ('formal_core_grant','formal_handicap_grant',
                                         'formal_single_grant','formal_protection_grant'))
    assert result['production_changed'] is False


@pytest.mark.parametrize('line,drawmargin,drawprob',[
    (-3,3,.0),(-2,2,.30),(-1,1,.10),(0,0,.30),
    (1,-1,.08),(2,-2,.07),(3,-3,.0)])
def test_each_official_integer_line_is_signed_correctly(line,drawmargin,drawprob):
    r=aggregate(rows(),line)
    assert r['let_draw_margin']==drawmargin
    assert r['exact_let_draw_probability']==pytest.approx(drawprob)
    assert r['jc_probabilities']['让平']==pytest.approx(drawprob)
    assert sum(r['jc_probabilities'].values())==pytest.approx(1)


@pytest.mark.parametrize('line',[-1,-2,-3,1,2,3])
def test_chinese_handicap_outcomes_partition_the_grid(line):
    r=aggregate(rows(),line)
    probs={'让胜':0,'让平':0,'让负':0}
    for x in rows():
        h,a=map(int,x['score'].split(':'))
        probs[jc_label(h,a,line)]+=x['probability']
    assert r['jc_probabilities']==pytest.approx(probs)


@pytest.mark.parametrize('line',[.5,-.75,1.5,'-1',True,4,-4])
def test_non_chinese_integer_line_forbidden(line):
    with pytest.raises(ValueError,match='integer'):
        aggregate(rows(),line)


def test_marginals_and_finite_scores_conserve_mass_without_refit():
    original=rows(); copy0=copy.deepcopy(original)
    r=aggregate(original,-1)
    assert original==copy0
    assert sum(r['wdl_probabilities'].values())==pytest.approx(1)
    assert sum(r['goal_bucket_probabilities'].values())==pytest.approx(1)
    assert sum(r['jc_probabilities'].values())==pytest.approx(1)
    assert sum(r['signed_margin_distribution'].values())==pytest.approx(1)
    assert r['raw_goal_bucket_top3']==['2','4','1']
    assert r['raw_integer_0_to_6_top3']==['2','4','1']
    assert r['raw_score_top3']==['2:0','2:2','1:0']
    assert r['probability_adjustment'] is False


def test_goal_top3_missing_from_score_top3_creates_only_challenger():
    # Goal 2 has three top exact scores; Goal 1 and Goal 3 are still high
    # aggregate buckets even though not represented by raw Score Top3.
    uneven=[('1:1',.20),('2:0',.16),('0:2',.14),('0:1',.12),
            ('1:0',.10),('2:1',.09),('1:2',.08),('0:0',.06),('4:0',.05)]
    r=aggregate([{'score':s,'probability':p} for s,p in uneven],-1)
    c=r['goal_anchor_challengers']
    assert [v['missing_goal_bucket'] for v in c]==['1','3']
    for v in c:
        assert v['candidate_mass']<=r['raw_score_top3_mass']+1e-12
        assert not v['auto_replace']
        assert v['loss_vs_unconstrained_global_top3']>=0
    assert r['top3_reordered'] is False


def test_signed_letdraw_top3_example_does_not_force_letdraw_pick():
    p=make_from_score_pairs(simple(),line=-1,frozen_pick='让负')
    result=inspect(p)
    w=result['S4_GS_RC_cross_layer_hardlock_v312']
    assert result['S4_GS_RC_unified_probability_bridge_v312']['exact_let_draw_probability']==pytest.approx(.35)
    assert 'MULTIPLE_TOP3_SCORES_POINT_TO_JC_LET_DRAW' in w['manual_review_reasons']
    assert w['official_frozen_jc_pick_unchanged']=='让负'
    assert w['research_jc_first']=='让负'
    assert w['handicap_single_eligible_for_automatic_grant'] is False
    assert result['automatic_direction_flip'] is False


def test_frozen_jc_opposes_integrated_jc_requires_review_not_flip():
    p=make_from_score_pairs(simple(),line=-1,frozen_pick='让胜')
    result=inspect(p)
    w=result['S4_GS_RC_cross_layer_hardlock_v312']
    assert w['research_jc_first']!=w['official_frozen_jc_pick_unchanged']
    assert 'FROZEN_JC_PICK_CONFLICTS_WITH_GRID_AGGREGATE' in w['manual_review_reasons']
    assert w['status']=='HANDICAP_MANUAL_REVIEW'


def test_high_tail_is_aggregate_7plus_not_exact_seven():
    r=aggregate(rows(),-1)
    assert r['goal_bucket_probabilities']['7+']==pytest.approx(.05)
    assert r['seven_plus_aggregate_not_exact_seven']
    assert goal_bucket(2,5)==goal_bucket(4,9)=='7+'
    assert r['raw_integer_0_to_6_top3']==['2','4','1']


def test_one_goal_and_zero_goal_probability_derive_from_score():
    r=aggregate(rows(),-1)
    assert r['goal_bucket_probabilities']['0']==pytest.approx(.05)
    assert r['goal_bucket_probabilities']['1']==pytest.approx(.18)
    z=next(c for c in r['goal_top3_to_score_top3_coverage'] if c['goal_bucket']=='1')
    assert z['highest_exact_score'] in ('1:0','0:1')


def test_missing_official_line_blocks_jc_without_asian_fallback():
    r=inspect(coherent_packet())
    z=r['S4_GS_RC_unified_probability_bridge_v312']
    w=r['S4_GS_RC_cross_layer_hardlock_v312']
    assert z['jc_probabilities'] is None
    assert z['wdl_probabilities'] is not None
    assert w['status']=='BLOCK_BAD_CROSS_LAYER_DATA'
    assert w['research_jc_first'] is None


def test_missing_matrix_blocks_all_joint_grants():
    r=inspect(pkt())
    assert r['S4_GS_RC_unified_probability_bridge_v312']['status'].startswith('UNKNOWN')
    assert r['S4_GS_RC_cross_layer_hardlock_v312']['status']=='BLOCK_NO_JOINT_GRID'
    assert r['formal_handicap_grant'] is None


def test_small_parent_wdl_mismatch_is_explicitly_blocked():
    p=coherent_packet()
    p['probabilities']=[.501,.299,.2]
    result=inspect(p)
    w=result['S4_GS_RC_cross_layer_hardlock_v312']
    assert 'FROZEN_WDL_NOT_EXACTLY_DERIVED_FROM_SAME_GRID' in w['blocking_reasons']
    assert result['outcome_probabilities_unchanged']==[.501,.299,.2]


def test_small_goal_mismatch_is_explicitly_blocked():
    p=coherent_packet();p['goal_distribution']['2']+=.001;p['goal_distribution']['4']-=.001
    result=inspect(p)
    assert 'FROZEN_RC_GOAL_BUCKETS_NOT_EXACTLY_DERIVED_FROM_SAME_GRID' in result['S4_GS_RC_cross_layer_hardlock_v312']['blocking_reasons']


@pytest.mark.parametrize('bad_rows',[
    [{'score':'1:0','probability':.8}],
    [{'score':'1:0','probability':.5},{'score':'1:0','probability':.5}],
    [{'score':'1:0','probability':float('nan')}],
    [{'score':'01:0','probability':1.0}],
    [{'score':'11:0','probability':1.0}],
    [{'score':'0:-1','probability':1.0}],
    [{'score':'0:0','probability':True}],
])
def test_bad_matrix_fail_closed(bad_rows):
    with pytest.raises(ValueError):aggregate(bad_rows,-1)


def test_0_001_mass_loss_not_silently_normalized():
    v=rows();v[0]['probability']-=.001
    with pytest.raises(ValueError,match='sum to 1'):
        aggregate(v,-1)


@pytest.mark.parametrize('field', ['actual_score','postmatch_20261116','recap_20261116','actual_handicap','match_events'])
def test_replay_only_fields_blocked_before_model_output(field):
    p=jc_pkt(-1);p[field]='x'
    with pytest.raises(ValueError,match='forbidden replay-only'):
        inspect(p)


def test_research_goals_do_not_reorder_original_scores():
    z=inspect(jc_pkt(-1))['S4_GS_RC_unified_probability_bridge_v312']
    assert z['raw_score_top3']==['2:0','2:2','1:0']
    assert isinstance(z['goal_anchor_challengers'],list)
    assert z['top3_reordered'] is False


def test_forward_freeze_evaluate_does_not_update_model_params():
    p,t=future_packet()
    p.update(official_handicap_line=-1,
             official_handicap_line_source={'basis':'official_jc_handicap',
                 'source_id':'official-test','observed_at':'2026-11-04T09:00:00+08:00'},
             frozen_handicap_pick='让负')
    old=copy.deepcopy(p)
    s=freeze(p,now=t)
    assert old==p
    assert s['joint_bridge_result']['raw_score_top3']==['2:0','2:2','1:0']
    a={'match_id':p['id'],'score':'2:0','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official-test-result','status':'final_90min'}
    row=evaluate(s,a)
    assert row['raw_grid_score_top3_hit'] is True
    assert row['raw_grid_goal_top3_hit'] is True
    assert row['bridge_jc_research_top1_hit'] is False  # -1 and win by 2: let win; -1 candidate let lose
    assert row['bridge_jc_actual']=='让胜'
    assert row['bridge_wdl_log_brier']['brier']>=0
    assert summary([row])['hits']['raw_grid_score_top3_hit']=={'hits':1,'n':1}
    assert not summary([row])['minimum_50_required_for_promotion_review']


def test_forward_snapshot_hash_detects_tamper():
    p,t=future_packet();s=freeze(p,now=t)
    s['joint_bridge_result']['raw_score_top3']=['0:0']
    a={'match_id':p['id'],'score':'0:0','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official','status':'final_90min'}
    with pytest.raises(ValueError,match='hash mismatch'):
        evaluate(s,a)


def test_forward_snapshot_denies_fake_postmatch():
    p,t=future_packet();s=freeze(p,now=t)
    a={'match_id':p['id'],'score':'2:2','observed_at':(t+timedelta(hours=1)).isoformat(),
       'source_id':'official','status':'final_90min'}
    with pytest.raises(ValueError,match='after 90-minute'):
        evaluate(s,a)


def test_no_real_date_dev_recap_automatically_certifies_gain():
    p,t=future_packet();s=freeze(p,now=t)
    a={'match_id':p['id'],'score':'2:2','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official','status':'final_90min'}
    row=evaluate(s,a)
    assert summary([row])['minimum_50_required_for_promotion_review'] is False
    with pytest.raises(ValueError,match='duplicate'):
        summary([row,row])


def test_dev16_is_not_a_new_forward_probability_sample():
    import json
    from pathlib import Path
    from replay_dev16_r6312 import audit
    src=Path(__file__).with_name('RECAP_DEV_20261116_CONVERSATION_ONLY_NOT_FORWARD_R6312.json')
    out=audit(json.loads(src.read_text(encoding='utf-8'))['matches'])
    assert out['n']==8
    assert out['actual_letdraw_count']==3
    assert out['published_jc_top1_hits']==2
    assert out['missing_goal_family_matches']==3
    assert out['multiple_scoretop3_letdraw_but_frozen_not_letdraw_count']==3
    assert out['auto_updated_or_refitted'] is False


def test_dev16_006_goal5_unrepresented_no_hindsight_boost():
    import json
    from pathlib import Path
    from replay_dev16_r6312 import audit
    src=Path(__file__).with_name('RECAP_DEV_20261116_CONVERSATION_ONLY_NOT_FORWARD_R6312.json')
    out=audit(json.loads(src.read_text(encoding='utf-8'))['matches'])
    r=next(x for x in out['matches'] if x['match_id']=='006')
    assert r['goal_top3_absent_from_score_top3']==['5']
    assert all(x['goal_bucket']!='5' for x in r['score_top3_mapping'])
    assert r['historical_chat_only_no_probability_matrix'] is True


@pytest.mark.parametrize('home_lambda,away_lambda',[(0.5,0.6),(1.0,1.2),(1.7,1.1),(2.4,1.8),(3.5,0.9),(0.7,3.0)])
def test_poisson_grid_conserves_all_joint_marginals(home_lambda,away_lambda):
    # Synthetic numerical property check; not a fitted real-match backtest.
    weights=[]
    for h in range(11):
        ph=math.exp(-home_lambda)*home_lambda**h/math.factorial(h)
        for a in range(11):
            pa=math.exp(-away_lambda)*away_lambda**a/math.factorial(a)
            weights.append((f'{h}:{a}',ph*pa))
    total=sum(p for _,p in weights)
    grid=[{'score':s,'probability':p/total} for s,p in weights]
    for line in (-3,-2,-1,1,2,3):
        x=aggregate(grid,line)
        assert sum(x['wdl_probabilities'].values())==pytest.approx(1,abs=1e-10)
        assert sum(x['goal_bucket_probabilities'].values())==pytest.approx(1,abs=1e-10)
        assert sum(x['jc_probabilities'].values())==pytest.approx(1,abs=1e-10)
        assert x['jc_probabilities']['让平']==pytest.approx(x['exact_let_draw_probability'],abs=1e-10)
        assert not x['top3_reordered']
