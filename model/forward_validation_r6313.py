"""R6.3.13 paired prematch freeze + postmatch scoring, never part of inspect.

All optional channels are snapshotted and scored on an external confirmed result.
Hash checks preserve local integrity, NOT trusted immutable third-party time.
"""
from __future__ import annotations
import math
from datetime import datetime
import forward_validation_r6311 as base
import forward_validation_r6312 as previous
import shadow_r6313
import joint_bridge_r6312 as joint

ORDER=joint.WDL
GOALS=joint.GOALS


def _rps(probs:dict,actual:str,ordered:tuple[str,...])->float:
    if actual not in ordered:raise ValueError('observed outcome outside ordered classes')
    pred=truth=error=0.
    for k in ordered[:-1]:
        pred+=probs[k];truth+=float(k==actual)
        error+=(pred-truth)**2
    return error/(len(ordered)-1)


def freeze(packet:dict,now:datetime|None=None)->dict:
    old=previous.freeze(packet,now=now)
    new=shadow_r6313.inspect(packet)
    b=new['S4_GS_RC_unified_probability_bridge_v312']
    rec={'schema':'M79_R6313_FORWARD_FREEZE_V1','r6312_snapshot':old,
         'match_id':old['match_id'],'kickoff':old['kickoff'],
         'score_matrix':packet.get('score_matrix') if b.get('status')=='ONE_JOINT_GRID_VALIDATED' else None,
         'research_candidate':new['research_candidate_grid_diagnostics_r6313'],
         'htft':new['HTFT_conditional_transition_r6313'],
         'market':new['market_devig_r6313'],
         'created_at_utc':old['created_at_utc'],
         'no_real_test_accuracy_claim':True}
    rec['snapshot_sha256']=base.digest(rec)
    return rec


def _check(snapshot:dict)->None:
    if not isinstance(snapshot,dict) or snapshot.get('schema')!='M79_R6313_FORWARD_FREEZE_V1':
        raise ValueError('invalid R6313 snapshot')
    data={k:v for k,v in snapshot.items() if k!='snapshot_sha256'}
    if snapshot.get('snapshot_sha256')!=base.digest(data):
        raise ValueError('R6313 snapshot hash mismatch')
    previous._check(snapshot['r6312_snapshot'])
    if snapshot['match_id']!=snapshot['r6312_snapshot']['match_id']:
        raise ValueError('snapshot match ID mismatch')


def evaluate(snapshot:dict,actual:dict)->dict:
    _check(snapshot)
    if not isinstance(actual,dict):raise ValueError('postmatch data required')
    optional={'half_time_score','half_time_source_id'}
    if not set(actual).issubset({'match_id','score','observed_at','source_id','status'}|optional):
        raise ValueError('unexpected postmatch data fields')
    if ('half_time_score' in actual)!=('half_time_source_id' in actual):
        raise ValueError('halftime score and source must be supplied together')
    core={k:v for k,v in actual.items() if k not in optional}
    prior=previous.evaluate(snapshot['r6312_snapshot'],core)
    ft=joint.wdl_label(*joint.parse_score(core['score']))
    br=snapshot['r6312_snapshot']['joint_bridge_result']
    linked=br.get('status')=='ONE_JOINT_GRID_VALIDATED'
    wdl_rps=goal_rps=score_log=None
    score_zero=None;htft_loss=None;htft_hit=None;market_losses=None
    if linked:
        h,a=joint.parse_score(core['score'])
        wdl_rps=_rps(br['wdl_probabilities'],ft,ORDER)
        goal_rps=_rps(br['goal_bucket_probabilities'],joint.goal_bucket(h,a),GOALS)
        probs={r['score']:r['probability'] for r in snapshot['score_matrix']}
        p=probs.get(core['score'],0.)
        score_zero=p==0
        score_log=-math.log(p) if p>0 else None
    ht=snapshot['htft']
    if 'half_time_score' in actual:
        if not isinstance(actual['half_time_source_id'],str) or not actual['half_time_source_id'].strip():
            raise ValueError('nonblank halftime source required')
        h1,a1=joint.parse_score(actual['half_time_score'])
        h,a=joint.parse_score(core['score'])
        if h1>h or a1>a:raise ValueError('halftime goals cannot exceed final goals')
        if ht.get('status')=='RESEARCH_HTFT_LINKED':
            label=joint.wdl_label(h1,a1)+ft
            p=ht['probabilities'][label]
            htft_loss=-math.log(p) if p>0 else None
            htft_hit=label in ht['top3']
    mk=snapshot['market']
    if mk.get('status')=='READ_ONLY_MARKET_BENCHMARK':
        market_losses={method:sum((p-float(k==ft))**2 for k,p in mk[method].items())
                       for method in ('multiplicative','power')}
    return {**prior,'snapshot_sha256_r6313':snapshot['snapshot_sha256'],
            'wdl_ranked_probability_score':wdl_rps,
            'goal_ranked_probability_score':goal_rps,
            'exact_score_log_loss':score_log,'actual_outside_grid_or_zero_mass':score_zero,
            'htft_log_loss':htft_loss,'htft_top3_hit':htft_hit,
            'market_brier_benchmarks':market_losses,'postmatch_scoring_only':True}


def summary(rows:list[dict])->dict:
    if len(set(x['match_id'] for x in rows))!=len(rows):raise ValueError('duplicate match id')
    metrics={}
    for key in ('wdl_ranked_probability_score','goal_ranked_probability_score',
                'exact_score_log_loss','htft_log_loss'):
        vals=[r[key] for r in rows if r.get(key) is not None]
        metrics[key]={'count':len(vals),'mean':math.fsum(vals)/len(vals) if vals else None}
    mh=[r['htft_top3_hit'] for r in rows if r.get('htft_top3_hit') is not None]
    exact_zero=sum(r.get('actual_outside_grid_or_zero_mass') is True for r in rows)
    return {'matches':len(rows),'metrics':metrics,
            'exact_score_zero_mass_events':exact_zero,
            'exact_score_log_loss_comparison_valid':exact_zero==0 and metrics['exact_score_log_loss']['count']==len(rows),
            'halftime_top3':{'hits':sum(mh),'n':len(mh)},
            'independent_external_frozen_samples_at_least_50':len(rows)>=50,
            'at_least_100_samples_preferred':len(rows)>=100,
            'no_claim_of_accuracy_improvement':True}
