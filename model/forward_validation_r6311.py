"""Immutable prematch snapshots and auditable postmatch paired evaluation.

The evaluator is NOT imported into the prematch inspector. It cannot affect
probabilities or selections. Capture at a real time preceding kickoff;
results arrive later in a separate object with verifiable provenance.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from typing import Any
import shadow_r6310
import shadow_r6311
import selection_efficiency_r633 as base
import shadow_r639


def canon(x:Any)->bytes:
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def digest(x:Any)->str:
    return sha256(canon(x)).hexdigest()


def _utc(s:str):
    return base._time(s,"timestamp").astimezone(timezone.utc)


def freeze(packet:dict, now:datetime|None=None)->dict:
    if not isinstance(packet,dict): raise ValueError('prematch input must be object')
    mid=packet.get('id')
    if not isinstance(mid,str) or not mid.strip():raise ValueError('nonblank match id required')
    if 'kickoff' not in packet or 'cutoff' not in packet:raise ValueError('cutoff and kickoff required')
    cutoff=_utc(packet['cutoff']);kickoff=_utc(packet['kickoff'])
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not cutoff<kickoff:raise ValueError('cutoff must be before kickoff')
    if not now<kickoff:raise ValueError('cannot create forward snapshot after kickoff')
    if now<cutoff:raise ValueError('snapshot cannot be created before declared data cutoff')
    old=shadow_r6310.inspect(packet)
    new=shadow_r6311.inspect(packet)
    score_new=new['GS1_8_forward_score_challengers']
    score_base=old['GS1_7_score_family_coverage_audit']['score_top3_unchanged'] if score_new['raw_global_top3'] is not None else None
    goal_base=old['RC2_5_exact_bucket_router'].get('shadow_top3')
    # Research only, score_top3 is never filled from results.
    record={'schema':'M79_R6311_FORWARD_FREEZE_V1',
            'match_id':mid,'cutoff':packet['cutoff'],'kickoff':packet['kickoff'],
            'created_at_utc':now.isoformat(),
            'input_packet_sha256':digest(packet),
            'matrix_provenance':new['score_matrix_provenance_audit_v311'],
            'baseline_model':'M79.3.6_Shadow_R6.3.10',
            'challenger_model':shadow_r6311.VERSION,
            'frozen_wdl_unchanged':old['outcome_probabilities_unchanged'],
            'baseline_score_top3':score_base,
            'baseline_goal_top3':goal_base,
            'challenger_score_top3':score_new.get('challengers'),
            'challenger_raw_top3':score_new.get('raw_global_top3'),
            'football_evidence_review':new['ESR_Form_v0_3_evidence_quality']['status'],
            'score_challenger_status':score_new['status'],
            'independent_validation_not_yet_performed':True,
            'formal_model_grant':None}
    record['snapshot_sha256']=digest(record)
    return record


def _check_snapshot(record:dict)->None:
    if not isinstance(record,dict) or record.get('schema')!='M79_R6311_FORWARD_FREEZE_V1':
        raise ValueError('invalid snapshot schema')
    original={k:v for k,v in record.items() if k!='snapshot_sha256'}
    if record.get('snapshot_sha256')!=digest(original):
        raise ValueError('snapshot hash mismatch: snapshot cannot be rewritten')
    created=_utc(record['created_at_utc']);kickoff=_utc(record['kickoff']);cutoff=_utc(record['cutoff'])
    if not cutoff<=created<kickoff:raise ValueError('snapshot must be created before kickoff and after cutoff')


def evaluate(snapshot:dict,actual:dict)->dict:
    _check_snapshot(snapshot)
    if not isinstance(actual,dict) or set(actual)!={'match_id','score','observed_at','source_id','status'}:
        raise ValueError('actual must have match_id score observed_at source_id status')
    if actual.get('match_id')!=snapshot['match_id']:raise ValueError('result match_id mismatch')
    if actual.get('status')!='final_90min':raise ValueError('only confirmed 90-minute result')
    if not isinstance(actual['source_id'],str) or not actual['source_id'].strip():
        raise ValueError('result source_id required')
    if _utc(actual['observed_at'])<_utc(snapshot['kickoff'])+timedelta(minutes=90):
        raise ValueError('result must be observed after 90-minute match')
    score=actual['score']
    if not isinstance(score,str):raise ValueError('score must be string')
    h,a=shadow_r639._score(score)
    goal=h+a
    baseline=snapshot['baseline_score_top3']
    challengers=snapshot['challenger_score_top3']
    hits={}
    for c in challengers or []:
        hits[c['name']]=score in c['score_top3']
    goal_top=snapshot.get('baseline_goal_top3')
    goal_hit=None
    if isinstance(goal_top,list):
        goal_hit=any(str(g)==str(goal) for g in goal_top)
    return {'match_id':snapshot['match_id'],'snapshot_sha256':snapshot['snapshot_sha256'],
            'actual_score':score,'actual_source_id':actual['source_id'],
            'actual_observed_at':actual['observed_at'],
            'original_score_top3_hit':None if baseline is None else score in baseline,
            'challenger_score_top3_hit':hits,
            'baseline_goal_top3_hit':goal_hit,
            'not_production_accuracy':True,'postmatch_data_never_entered_prematch_inspect':True}


def summary(scored:list[dict])->dict:
    if not isinstance(scored,list):raise ValueError('scored must be list')
    mids=[r['match_id'] for r in scored]
    if len(mids)!=len(set(mids)):raise ValueError('duplicate match id in evaluation batch')
    base=[r['original_score_top3_hit'] for r in scored if r['original_score_top3_hit'] is not None]
    cand={}
    for r in scored:
        for k,v in r['challenger_score_top3_hit'].items():cand.setdefault(k,[]).append(v)
    n=len(base)
    return {'matches':len(scored),'eligible_score_pairs':n,
            'baseline_score_top3':{'hits':sum(base),'n':n},
            'challengers':{k:{'hits':sum(v),'n':len(v),
                               'delta_hits_vs_baseline':sum(v)-sum(base) if len(v)==n else None}
                           for k,v in sorted(cand.items())},
            'sufficient_for_promotion_screen':len(scored)>=50,
            'preferred_100_match_observation_reached':len(scored)>=100,
            'no_accuracy_gain_claim_below_independent_sample':True}
