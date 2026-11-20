"""Authorized offline paired HTFT benchmark. Never fetches external match data."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
import random
from pathlib import Path
from htft_transition_v2_r636 import _dt, _grid, _score, fit_logits, predict, evaluate


def _quantile(xs, q):
    v = sorted(xs)
    pos = q * (len(v)-1)
    lo = int(pos)
    return v[lo] * (1-(pos-lo)) + v[min(lo+1,len(v)-1)] * (pos-lo)


def _paired_ci(values, replicates=1500):
    if not values:raise ValueError('paired records missing')
    rng = random.Random(6316)
    n = len(values)
    reps = [sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(replicates)]
    return {'mean_candidate_minus_baseline':sum(values)/n,
            'bootstrap_95pct_interval':[_quantile(reps,.025),_quantile(reps,.975)]}


def _validate(rec):
    keys={'match_id','kickoff','cutoff','source_observed_at','score_matrix','full_time_score','half_time_score'}
    if not isinstance(rec,dict) or set(rec)!=keys:
        raise ValueError('fixture requires identity, source and frozen cutoff, complete score grid, final and half scores')
    if not isinstance(rec['match_id'],str) or not rec['match_id']:
        raise ValueError('match_id required')
    if not _dt(rec['source_observed_at'])<=_dt(rec['cutoff'])<_dt(rec['kickoff']):
        raise ValueError('source and prediction cutoff must precede kickoff')
    _grid(rec['score_matrix'])
    h,a = _score(rec['full_time_score']); hh,ha=_score(rec['half_time_score'])
    if hh>h or ha>a:raise ValueError('infeasible half/full score')


def run(dataset):
    if not isinstance(dataset,dict) or set(dataset)!={'authorized_for_analysis','development','holdout'} or dataset['authorized_for_analysis'] is not True:
        raise ValueError('explicitly authorized dataset with development and holdout required')
    dev=dataset['development'];test=dataset['holdout']
    if not isinstance(dev,list) or not isinstance(test,list) or not dev or not test:
        raise ValueError('nonempty chronological development and untouched holdout required')
    ids=[]
    for r in dev+test:
        _validate(r);ids.append(r['match_id'])
    if len(set(ids))!=len(ids):raise ValueError('duplicate across development and holdout')
    last_dev=max(_dt(x['kickoff']) for x in dev)
    first_test=min(_dt(x['source_observed_at']) for x in test)
    if not last_dev < first_test:
        raise ValueError('training matches must precede all holdout observations')
    fh_h = sum(_score(r['half_time_score'])[0] for r in dev)
    fa_h = sum(_score(r['half_time_score'])[1] for r in dev)
    fh_f = sum(_score(r['full_time_score'])[0] for r in dev)
    fa_f = sum(_score(r['full_time_score'])[1] for r in dev)
    fh = (fh_h+45.)/(fh_f+100.)
    fa = (fa_h+45.)/(fa_f+100.)
    history=[{k:r[k] for k in ('match_id','kickoff','full_time_score','half_time_score')} for r in dev]
    calibrated=fit_logits(history,fraction_home=fh,fraction_away=fa,asof_cutoff=first_test.isoformat())
    paired=[];classes=Counter()
    for r in test:
        params=dict(fraction_home=fh,fraction_away=fa,source_id=r['match_id'],
                    observed_at=r['source_observed_at'],cutoff=r['cutoff'],kickoff=r['kickoff'])
        original=predict(r['score_matrix'],**params)
        challenger=predict(r['score_matrix'],**params,
            transition_logits=calibrated['transition_logits'],
            latest_training_kickoff=calibrated['latest_training_kickoff'])
        if original['full_time_wdl']!=challenger['full_time_wdl']:
            raise AssertionError('prematch fulltime probabilities changed')
        b=evaluate(original,full_time_score=r['full_time_score'],half_time_score=r['half_time_score'])
        c=evaluate(challenger,full_time_score=r['full_time_score'],half_time_score=r['half_time_score'])
        classes[b['actual']]+=1
        paired.append({'base':b,'challenger':c})
    def summarize(side):
        return {'log_loss':sum(x[side]['log_loss'] for x in paired)/len(paired),
                'brier':sum(x[side]['brier'] for x in paired)/len(paired),
                'top1_hits':sum(x[side]['top1_hit'] for x in paired),
                'top2_hits':sum(x[side]['top2_hit'] for x in paired),
                'top3_hits':sum(x[side]['top3_hit'] for x in paired)}
    base=summarize('base');cand=summarize('challenger')
    return {'status':'RETROSPECTIVE_HOLDOUT_RESEARCH_ONLY',
            'n_development':len(dev),'n_holdout':len(test),
            'historical_fraction_home':fh,'historical_fraction_away':fa,
            'ridge':15.,'observed_classes':dict(classes),
            'baseline':base,'candidate':cand,
            'logloss_paired_ci':_paired_ci([x['challenger']['log_loss']-x['base']['log_loss'] for x in paired]),
            'brier_paired_ci':_paired_ci([x['challenger']['brier']-x['base']['brier'] for x in paired]),
            'tradeoff':'Neither a higher hit rate alone nor improved loss alone grants promotion',
            'candidate_better_both_losses':cand['log_loss']<base['log_loss'] and cand['brier']<base['brier'],
            'formal_grant':None,'independent_M79_production_certified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset');p.add_argument('--output');args=p.parse_args()
    r=run(json.loads(Path(args.dataset).read_text(encoding='utf-8')))
    output=json.dumps(r,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(output,encoding='utf-8')
    else:print(output)
if __name__=='__main__':main()
