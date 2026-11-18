import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from shadow_r6311 import inspect,VERSION
from forward_validation_r6311 import freeze,evaluate,summary
from replay_conversation_r6311 import audit_dev14
from test_motivation_squad_r634 import pkt, BEFORE
from test_shadow_r637 import coherent_packet
from test_shadow_r639 import jc_pkt


def ev(family='form', side='home', certainty='confirmed', signal='home',
       event_id='form1', opponent_adjusted=True, stamp=BEFORE, **kw):
    x={'family':family,'side':side,'certainty':certainty,'signal':signal,
       'event_id':event_id,'source_id':'team-official','observed_at':stamp}
    if family=='form':x['opponent_adjusted']=opponent_adjusted
    if family in ('squad','replacement'):x['replacement_quality']=kw.pop('replacement_quality','unknown')
    return {**x,**kw}


def provenance(channel='hybrid', stamp=BEFORE):
    return {'channel':channel, 'source_id':'prior-model-record','observed_at':stamp,'model_id':'test-only-prior'}


def future_packet():
    t=datetime.now(timezone.utc)
    p=coherent_packet()
    p['id']='TEST-SYNTHETIC-001'
    p['cutoff']=(t-timedelta(minutes=10)).isoformat()
    p['kickoff']=(t+timedelta(hours=3)).isoformat()
    return p,t


def test_parent_immutability_and_no_formal_grants():
    p=jc_pkt(-1); old=copy.deepcopy(p);res=inspect(p)
    assert p==old
    assert res['version']==VERSION
    assert res['outcome_probabilities_unchanged']==[.5,.3,.2]
    assert res['GS1_8_forward_score_challengers']['raw_global_top3']['score_top3']==['2:0','2:2','1:0']
    assert all(res[k] is None for k in ('formal_single_grant','formal_protection_grant','formal_core_grant','formal_handicap_grant'))
    assert res['probability_adjustment_applied'] is False
    assert res['production_changed'] is False


def test_frozen_no_joint_does_not_fabricate_challengers():
    res=inspect(pkt())
    assert res['GS1_8_forward_score_challengers']['status'].startswith('UNKNOWN')
    assert res['GS1_8_forward_score_challengers']['challengers'] is None
    assert res['score_matrix_provenance_audit_v311']['status']=='UNKNOWN_MATRIX_SOURCE'
    assert res['Selection_Context_v0_9_forward_hygiene']['formal_direction_grant'] is None


def test_lineup_replacement_group_deduped_and_no_rating_inference():
    p=pkt();p['football_evidence_v311']=[
      ev('squad', event_id='loss-1',replacement_quality='unknown'),
      ev('replacement', event_id='loss-1',replacement_quality='unknown')]
    x=inspect(p)['ESR_Form_v0_3_evidence_quality']
    assert x['unique_causal_events']==1
    assert x['independent_groups']==['roster']
    assert x['events'][1]['deduplicated'] is True
    assert 'DUPLICATE_CAUSAL_EVENT_NOT_DOUBLE_COUNTED' in x['flags']
    assert 'UNVERIFIED_REPLACEMENT_QUALITY_NO_STRENGTH_INFERENCE' in x['flags']
    assert x['new_risk_family_votes']==0


def test_uncorrected_recent_form_is_flagged_without_direction_flip():
    p=pkt(p=(.22,.18,.60));p['football_evidence_v311']=[ev(opponent_adjusted=False)]
    x=inspect(p)
    assert 'UNADJUSTED_FORM_NEEDS_OPPONENT_QUALITY_REVIEW' in x['audit_flags_r6311']
    assert x['Selection_Context_v0_9_forward_hygiene']['core_review_only'] is True
    assert x['outcome_probabilities_unchanged']==[.22,.18,.60]
    assert x['automatic_direction_flip'] is False


def test_adjusted_confirmed_form_does_not_create_new_risk_vote():
    p=pkt();p['football_evidence_v311']=[ev()]
    x=inspect(p)['ESR_Form_v0_3_evidence_quality']
    assert x['status']=='SOURCE_TIME_DEDUP_AUDITED'
    assert x['core_manual_review'] is False
    assert x['independent_groups']==['form']
    assert x['new_risk_family_votes']==0


@pytest.mark.parametrize('update',[
    [ev(stamp='2026-11-04T13:00:00+08:00')],
    [dict(ev(family='tactics'),opponent_adjusted=True)],
    [ev(certainty='free-floating')],
    [ev(event_id='')],
    [ev(replacement_quality='great')],
])
def test_invalid_football_evidence_fails_closed(update):
    p=pkt();p['football_evidence_v311']=update
    with pytest.raises(ValueError):inspect(p)


def test_duplicate_conflicting_event_is_rejected():
    p=pkt();p['football_evidence_v311']=[ev(event_id='x'),ev(event_id='x',side='away')]
    with pytest.raises(ValueError,match='contradictory'):inspect(p)


def test_provenance_football_only_with_market_data_refused():
    p=pkt();p['matrix_provenance_v311']=provenance('football_only')
    p['evidence']=[{'family':'market_price','state':'neutral','source_id':'market','observed_at':BEFORE}]
    with pytest.raises(ValueError,match='conflicts'):inspect(p)


def test_market_channel_does_not_get_football_only_certification():
    p=coherent_packet();p['matrix_provenance_v311']=provenance('market_only')
    x=inspect(p)['score_matrix_provenance_audit_v311']
    assert x['declared_channel']=='market_only'
    assert x['football_only_claim_verified'] is False


def test_provenance_future_rejected():
    p=pkt();p['matrix_provenance_v311']=provenance(stamp='2026-11-05T11:00:00+08:00')
    with pytest.raises(ValueError,match='post-cutoff'):inspect(p)


def test_diversity_is_only_shadow_and_mass_can_be_lower():
    # Synthetic coherent matrix with all global Top3 in home-win family.
    rows=[('1:0',.18),('2:0',.17),('3:0',.15)]
    rows += [(f'{i}:{i}',.05) for i in range(6)]
    rows += [('0:1',.05),('0:2',.05),('1:2',.05),('2:3',.05)]
    p=coherent_packet()
    p['score_matrix']=[{'score':s,'probability':m} for s,m in rows]
    g={str(i):0.0 for i in range(7)};g['7+']=0.0
    for s,m in rows:
        h,a=map(int,s.split(':'));n=h+a
        g[str(n) if n<=6 else '7+']+=m
    p['goal_distribution']=g
    x=inspect(p)['GS1_8_forward_score_challengers']
    raw=x['raw_global_top3']
    assert raw['wdl_families']==['胜']
    div=x['challengers'][0]
    assert div['score_top3_changed'] is True
    assert len(div['wdl_families'])==2
    assert div['selected_joint_mass']<=raw['selected_joint_mass']
    assert div['loss_vs_global_top3']>0
    assert x['score_top3_automatic_replacement'] is False


def test_jc_margin_challenger_requires_official_line():
    no=inspect(coherent_packet())['GS1_8_forward_score_challengers']
    yes=inspect(jc_pkt(-1))['GS1_8_forward_score_challengers']
    assert len(no['challengers'])==2
    assert len(yes['challengers'])==3


def test_seven_plus_not_represented_as_exact_seven_goal():
    x=inspect(coherent_packet())['GS1_8_forward_score_challengers']
    assert x['tail_score_watch']['seven_plus_goals']['score']=='0:7'
    assert x['tail_score_watch']['five_six_goals'] is None
    assert x['raw_global_top3_is_optimal_for_matrix'] is True


@pytest.mark.parametrize('field',('actual_score','actual_final_score','final_score','result_timestamp','in_play_events'))
def test_prematch_replay_fields_rejected(field):
    p=pkt();p[field]='x'
    with pytest.raises(ValueError,match='forbidden postmatch'):inspect(p)


def test_true_forward_freeze_and_eval_is_separate_and_hashed():
    p,t=future_packet()
    snapshot=freeze(p,now=t)
    assert snapshot['baseline_score_top3']==['2:0','2:2','1:0']
    assert snapshot['created_at_utc']
    actual={'match_id':p['id'],'score':'2:0',
            'observed_at':(t+timedelta(hours=5)).isoformat(),
            'source_id':'official-match-report','status':'final_90min'}
    row=evaluate(snapshot,actual)
    assert row['original_score_top3_hit'] is True
    assert row['challenger_score_top3_hit']['wdl_family_diversity_candidate'] is True
    summ=summary([row])
    assert summ['eligible_score_pairs']==1
    assert summ['sufficient_for_promotion_screen'] is False
    assert summ['baseline_score_top3']['hits']==1


def test_forward_freeze_rejects_after_kickoff():
    p,t=future_packet()
    with pytest.raises(ValueError,match='after kickoff'):
        freeze(p,now=t+timedelta(hours=4))


def test_forward_freeze_rejects_created_before_cutoff():
    p,t=future_packet()
    with pytest.raises(ValueError,match='before declared data cutoff'):
        freeze(p,now=t-timedelta(hours=1))


def test_tampered_snapshot_cannot_be_evaluated():
    p,t=future_packet();s=freeze(p,now=t)
    s['baseline_score_top3']=['2:1','2:0','1:0']
    actual={'match_id':p['id'],'score':'2:0',
            'observed_at':(t+timedelta(hours=5)).isoformat(),
            'source_id':'official','status':'final_90min'}
    with pytest.raises(ValueError,match='hash mismatch'):evaluate(s,actual)


def test_result_not_final_or_too_early_refused():
    p,t=future_packet();s=freeze(p,now=t)
    actual={'match_id':p['id'],'score':'1:0',
            'observed_at':(t+timedelta(hours=3,minutes=10)).isoformat(),
            'source_id':'source','status':'final_90min'}
    with pytest.raises(ValueError,match='after 90-minute'):evaluate(s,actual)
    actual['status']='live'
    with pytest.raises(ValueError,match='confirmed'):evaluate(s,actual)


def test_batch_duplicate_ids_rejected():
    p,t=future_packet();s=freeze(p,now=t)
    actual={'match_id':p['id'],'score':'2:0',
            'observed_at':(t+timedelta(hours=5)).isoformat(),'source_id':'official','status':'final_90min'}
    row=evaluate(s,actual)
    with pytest.raises(ValueError,match='duplicate'):summary([row,row])


def test_conversation_14_recap_is_development_not_forward():
    f=Path(__file__).with_name('RECAP_20261114_14_MATCHES_CONVERSATION_ONLY_DEV.json')
    rows=json.loads(f.read_text(encoding='utf-8'))
    a=audit_dev14(rows)
    assert a['n']==14
    assert a['metrics']=={
      'wdl_hit':{'hits':8,'n':14},'score_top1_hit':{'hits':0,'n':14},
      'score_top3_hit':{'hits':5,'n':14},'goal_top3_hit':{'hits':8,'n':14}}
    assert a['eligible_for_independent_validation'] is False


def test_prematch_cannot_accept_development_recap():
    p=pkt();p['recap']={'id':'003','actual_score':'3:2'}
    with pytest.raises(ValueError):inspect(p)
