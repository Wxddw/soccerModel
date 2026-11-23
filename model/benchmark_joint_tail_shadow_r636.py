"""True chronological holdout benchmark for joint score candidate (never an auto grant).

Requires authorized historical frozen prematch Q + actual results. No train-test
mixing, no using results as pregame features, no selection after seeing holdout.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
from joint_tail_calibration_shadow_r636 import (
    fit, predict, grid, aggregates, score, timestamp, _wdl, WDL,
)


def _loss(distribution, actual):
    if actual not in distribution:
        raise ValueError('actual outcome absent from distribution')
    p=distribution[actual]
    return -math.log(max(p,1e-15)), 1.-2.*p+math.fsum(x*x for x in distribution.values())


def _case(g, actual, line):
    a=aggregates(g,line)
    h,away=score(actual)
    s=f'{h}:{away}'
    raw={f'{x}:{y}':p for (x,y),p in g.items()}
    goal=str(h+away) if h+away <=6 else '7+'
    jc='让胜' if h+line-away>0 else '让平' if h+line-away==0 else '让负'
    v={}
    for prefix,distribution,label,top in [
        ('score',raw,s,a['score_top3']),
        ('goal',a['goals'],goal,a['goal_top3']),
        ('jc',a['jc'],jc,sorted(a['jc'],key=lambda k:-a['jc'][k]))]:
        v[prefix+'_ll'],v[prefix+'_brier']=_loss(distribution,label)
        v[prefix+'_top1']=label==top[0]
        v[prefix+'_top3']=label in top[:3]
    v['goal_dual']=goal in a['goal_dual']
    v['outcome']=_wdl(h,away)
    v['wdl']=a['wdl']
    return v


def _summary(rows):
    keys=('score_ll','score_brier','score_top1','score_top3',
          'goal_ll','goal_brier','goal_top1','goal_top3','goal_dual',
          'jc_ll','jc_brier','jc_top1')
    return {'n':len(rows),**{key:sum(x[key] for x in rows)/len(rows) for key in keys}}


def _bootstrap(a, b, key, samples=1200):
    delta=[y[key]-x[key] for x,y in zip(a,b)]
    n=len(delta);randomizer=random.Random(6361123)
    res=sorted(math.fsum(delta[randomizer.randrange(n)] for _ in range(n))/n for _ in range(samples))
    return {'challenger_minus_baseline':math.fsum(delta)/n,
            'paired_bootstrap95':[res[int((samples-1)*.025)],res[int((samples-1)*.975)]]}


def run(payload):
    if not isinstance(payload,dict) or set(payload)!={'authorized_for_analysis','development','holdout','calibration_id'} or payload['authorized_for_analysis'] is not True:
        raise ValueError('complete explicitly authorized split file required')
    dev=payload['development'];test=payload['holdout']
    if not isinstance(dev,list) or not isinstance(test,list) or not dev or not test:
        raise ValueError('both chronological splits required')
    ids=[]
    for row in dev+test:
        if not isinstance(row,dict) or not isinstance(row.get('match_id'),str):
            raise ValueError('match id required in both splits')
        ids.append(row['match_id'])
    if len(set(ids))!=len(ids):raise ValueError('duplicate match across dev/holdout')
    earliest=min(timestamp(row['observed_at']) for row in test)
    fitted=fit(dev,asof_cutoff=earliest.isoformat(),calibration_id=payload['calibration_id'])
    old=[];new=[];seen=Counter()
    for row in sorted(test,key=lambda r:timestamp(r['kickoff'])):
        expected={'match_id','source_id','observed_at','cutoff','kickoff','result_observed_at',
                  'score_matrix','actual_score','official_jc_line','authorized_for_analysis'}
        if set(row)!=expected or row['authorized_for_analysis'] is not True:
            raise ValueError('complete licensed holdout scoring row required')
        if not timestamp(row['observed_at'])<=timestamp(row['cutoff'])<timestamp(row['kickoff'])<timestamp(row['result_observed_at']):
            raise ValueError('non-chronological holdout outcome or source')
        p={k:row[k] for k in ('match_id','source_id','observed_at','cutoff','kickoff','score_matrix','official_jc_line')}
        candidate=predict(p,fitted)
        q=grid(row['score_matrix'])
        newer=grid(candidate['candidate_score_grid'])
        a=_case(q,row['actual_score'],row['official_jc_line'])
        b=_case(newer,row['actual_score'],row['official_jc_line'])
        for label in WDL:
            if abs(a['wdl'][label]-b['wdl'][label])>1e-10:
                raise AssertionError('WDL upstream margin changed')
        old.append(a);new.append(b)
        seen[candidate['regime']]+=1
    comparisons={key:_bootstrap(old,new,key) for key in ('score_ll','score_brier',
                                                           'goal_ll','goal_brier','jc_ll','jc_brier')}
    return {'status':'CHRONOLOGICAL_OFFLINE_SHADOW_ONLY','research_only':True,
            'formal_grant':None,'production_changed':False,
            'development_n':len(dev),'holdout_n':len(test),
            'holdout_by_regime':dict(seen),
            'baseline':_summary(old),'challenger':_summary(new),
            'paired_differences':comparisons,
            'upstream_outcome_locked':True,
            'certified_improvement':False,
            'limitations':['No final-score benchmark authorizes automatically changing production picks',
                           'Provider match-level source timestamp and data-use permission must be independently verified',
                           'HTFT must be separately recomputed from the same candidate Q before any downstream experiment',
                           'Study needs broad, nonselected league and kickoff cohorts and robust across-regime checks']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset')
    p.add_argument('--output')
    args=p.parse_args()
    outcome=run(json.loads(Path(args.dataset).read_text(encoding='utf-8')))
    content=json.dumps(outcome,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(content,encoding='utf-8')
    else:print(content)

if __name__=='__main__':main()
