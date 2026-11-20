"""Offline paired benchmark: neutral six-period HTFT vs learned state-aware HTFT.

Authorized real prematch snapshots + actual timestamped scoring events required.
Does not scrape, invent Q, train on the test set, or promote Production.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
from htft_segment_hazard_r636 import _time,_historical,_prob_grid,_score,_wdl,predict,fit,FACTOR_KEYS,PATHS


def _metrics(items):
    n=len(items)
    return {'n':n,'log_loss':sum(x['log_loss'] for x in items)/n,
            'brier':sum(x['brier'] for x in items)/n,
            'top1_hits':sum(x['top1_hit'] for x in items),
            'top2_hits':sum(x['top2_hit'] for x in items),
            'top3_hits':sum(x['top3_hit'] for x in items)}


def _score_one(out,ht,ft):
    h,a=_score(ft);hh,ha=_score(ht)
    if hh>h or ha>a:raise ValueError('invalid actual half/full score')
    key=_wdl(hh,ha)+_wdl(h,a)
    v=out['probabilities']
    return {'actual':key,'log_loss':-math.log(max(v[key],1e-15)),
            'brier':math.fsum((p-(k==key))**2 for k,p in v.items()),
            'top1_hit':out['top1']==key,'top2_hit':key in out['top2'],
            'top3_hit':key in out['top3']}


def _ci(diffs,repeats=800):
    rng=random.Random(63620);n=len(diffs)
    values=sorted(sum(diffs[rng.randrange(n)] for _ in range(n))/n for _ in range(repeats))
    return {'candidate_minus_baseline_mean':sum(diffs)/n,
            'bootstrap_95pct':[values[int(.025*(repeats-1))],values[int(.975*(repeats-1))]]}


def run(data):
    if not isinstance(data,dict) or set(data)!={'authorized_for_analysis','development','holdout'} or data['authorized_for_analysis'] is not True:
        raise ValueError('explicitly authorized development/holdout dataset required')
    dev=data['development'];hold=data['holdout']
    if not isinstance(dev,list) or not isinstance(hold,list) or not dev or not hold:
        raise ValueError('nonempty chronological paired splits required')
    ids=[r['match_id'] for r in dev+hold]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate match across splits')
    start=min(_time(r['observed_at']) for r in hold)
    fit_records=[{k:v for k,v in r.items() if k!='score_matrix'} for r in dev]
    training=fit(fit_records,asof_cutoff=start.isoformat())
    base=[];chall=[];classes=Counter()
    for r in hold:
        if set(r)!=set(fit_records[0])|{'score_matrix'}:
            raise ValueError('holdout requires fully timestamped Q and outcome events')
        _historical({k:v for k,v in r.items() if k!='score_matrix'},
                    _time(r['result_observed_at']) + __import__('datetime').timedelta(seconds=1))
        _prob_grid(r['score_matrix'])
        if not _time(training['latest_training_result_observed_at'])<=_time(r['observed_at']):
            raise ValueError('test source predates availability of training results')
        params={k:r[k] for k in ('observed_at','cutoff','kickoff','home_xg','away_xg')}
        params.update({'source_id':r['match_id'], 'calibration_id':'development-event-timing',
                       'latest_training_result_observed_at':training['latest_training_result_observed_at'],
                       'home_shares':training['home_shares'],'away_shares':training['away_shares']})
        simple=predict(r['score_matrix'],{**params,'state_factors':{k:1. for k in FACTOR_KEYS}})
        dynamic=predict(r['score_matrix'],{**params,'state_factors':training['state_factors']})
        for w in ('胜','平','负'):
            if abs(simple['full_time_wdl'][w]-dynamic['full_time_wdl'][w])>1e-9:
                raise AssertionError('FT Q changed between paired versions')
        b=_score_one(simple,r['half_time_score'],r['full_time_score'])
        c=_score_one(dynamic,r['half_time_score'],r['full_time_score'])
        base.append(b);chall.append(c);classes[b['actual']]+=1
    bm=_metrics(base);cm=_metrics(chall)
    return {'status':'CHRONOLOGICAL_RESEARCH_ONLY','formal_grant':None,
            'n_development':len(dev),'n_holdout':len(hold),'class_counts':dict(classes),
            'baseline_neutral_six_period':bm,'candidate_score_state':cm,
            'log_loss_delta_ci':_ci([c['log_loss']-b['log_loss'] for b,c in zip(base,chall)]),
            'brier_delta_ci':_ci([c['brier']-b['brier'] for b,c in zip(base,chall)]),
            'candidate_both_losses_better':cm['log_loss']<bm['log_loss'] and cm['brier']<bm['brier'],
            'note':'Snapshot times and data licenses are self-declared until independently audited. No M79 Production claims.'}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('dataset');cli.add_argument('--output');args=cli.parse_args()
    result=run(json.loads(Path(args.dataset).read_text(encoding='utf-8')))
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(txt,encoding='utf-8')
    else:print(txt)
if __name__=='__main__':main()
