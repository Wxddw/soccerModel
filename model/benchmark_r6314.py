"""Offline five-module benchmark runner, R6.3.14.

Reads ONLY a user-provided, lawfully obtainable JSON fixture dataset with
prematch score matrices and before-cutoff provenance. Never fetches data,
trains Production, or reconstructs historical pregame Q from final scores.

JSON root: {"development": [fixture...], "test": [fixture...]}
Required fixture: match_id, kickoff, cutoff, score_matrix, result_score.
Optional: half_time_score, market_snapshot, official_jc_integer_line,
          candidate_specs (four spec objects for four R6.3.13 models).
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import calibration_r6314 as c
import candidate_models_r6313 as models
import joint_bridge_r6312 as joint
import market_audit_r6313 as market

REQUIRED=('match_id','kickoff','cutoff','score_matrix','result_score')
CANDIDATES=models.MODELS


def _mean(xs):return math.fsum(xs)/len(xs) if xs else None


def _core(x):
    if not all(k in x for k in REQUIRED): raise ValueError('all fixtures require full historic Q and prediction cutoff')
    return {k:x[k] for k in REQUIRED}


def _model_spec(x,model):
    specs=x.get('candidate_specs')
    if not isinstance(specs,dict) or set(specs)!=set(CANDIDATES):return None
    spec=specs[model]
    if spec.get('model')!=model or spec.get('kickoff')!=x['kickoff']:
        raise ValueError('candidate model or fixture mismatch')
    if models._asof(spec['observed_at'])>models._asof(x['cutoff']):
        raise ValueError('candidate generated from after cutoff')
    return spec


def run(payload:dict)->dict:
    if not isinstance(payload,dict) or set(payload)!={'development','test'}:raise ValueError('development and test required')
    dev,test=payload['development'],payload['test']
    cdev,ctest=[_core(x) for x in dev],[_core(x) for x in test]
    c.check_train_test(cdev,ctest)
    r={'schema':'SHADOW_R6314_FIVE_MODULE_RESEARCH_V1',
       'development_n':len(dev),'future_test_n':len(test),
       's4':c.evaluate_chronological(cdev,ctest,'margin'),
       'rc':c.evaluate_chronological(cdev,ctest,'goal'),
       'GS':{'status':'BLOCK_NO_FULL_PREMATCH_CANDIDATE_SPECS'},
       'HTFT':{'status':'BLOCK_MISSING_HALF_TIME_HISTORY'},
       'Outcome':{'status':'BLOCK_MISSING_TIMESTAMPED_QUOTES'},
       'JC':{'status':'NO_OFFICIAL_JC_LINES'},
       'formal_grant':None,'production_changed':False,
       'test_not_used_for_parameter_selection':True}
    if all(_model_spec(x,m) is not None for x in dev+test for m in CANDIDATES):
        sc={};selected={}
        for m in CANDIDATES:
            d=[c.score_grid(models.generate_grid(_model_spec(x,m))['grid'],x['result_score'])['score_log_loss'] for x in dev]
            t=[c.score_grid(models.generate_grid(_model_spec(x,m))['grid'],x['result_score']) for x in test]
            sc[m]={'development_score_log_loss':_mean(d),'test_score_log_loss':_mean([v['score_log_loss'] for v in t]),
                   'test_score_top3_hits':sum(v['score_top3_hit'] for v in t),
                   'test_goal_rps':_mean([v['goal']['ranked_probability_score'] for v in t])}
        choice=min(CANDIDATES,key=lambda m:sc[m]['development_score_log_loss'])
        r['GS']={'status':'CHRONOLOGICAL_RESEARCH_COMPARISON',
                 'dev_selected_model':choice,'candidate_results':sc,
                 'no_inference_of_production_improvement':True}
    elif any('candidate_specs' in x for x in dev+test):
        r['GS']['note']='incomplete per-fixture model set: blocked instead of inventing data'
    if all('half_time_score' in x for x in dev+test):
        hist=[{'kickoff':x['kickoff'],'full_time_score':x['result_score'],
               'half_time_score':x['half_time_score']} for x in dev]
        prior=c.fit_halftime_prior(hist,min(models._asof(x['cutoff']) for x in test).isoformat())
        end=max(models._asof(x['kickoff']) for x in dev)
        base=[];chal=[];base_hit=chal_hit=0
        for x in test:
            common={'source_id':'past-confirmed-half-times-RESEARCH','observed_at':end.isoformat(),
                    'kickoff':x['kickoff']}
            b=c.score_htft(x['score_matrix'],x['result_score'],x['half_time_score'],
                           {**common,'fraction_home':.5,'fraction_away':.5})
            v=c.score_htft(x['score_matrix'],x['result_score'],x['half_time_score'],
                           {**common,'fraction_home':prior['fraction_home'],'fraction_away':prior['fraction_away']})
            base.append(b['log_loss']);chal.append(v['log_loss'])
            base_hit+=b['top3_hit'];chal_hit+=v['top3_hit']
        r['HTFT']={'status':'CHRONOLOGICAL_RESEARCH_COMPARISON',
                   'prior':prior,'baseline_log_loss':_mean(base),'candidate_log_loss':_mean(chal),
                   'baseline_top3_hits':base_hit,'candidate_top3_hits':chal_hit}
    if all('market_snapshot' in x for x in test):
        mod=[];multi=[];power=[];lags=[]
        for x in test:
            mk=x['market_snapshot']
            if mk['kickoff']!=x['kickoff']:raise ValueError('market/fixture mismatch')
            a=c.compare_same_cutoff(x['score_matrix'],mk,x['cutoff']);lags.append(a['quote_delay_seconds'])
            y=joint.wdl_label(*joint.parse_score(x['result_score']))
            mod.append(c._stats(a['model_probabilities'],y,joint.WDL))
            multi.append(c._stats(a['market_mul'],y,joint.WDL))
            power.append(c._stats(a['market_power'],y,joint.WDL))
        r['Outcome']={'status':'TIMESTAMP_CHECKED_PAIR_COMPARISON',
                      'test_n':len(test),
                      'mean_quote_delay_seconds':_mean(lags),
                      'model':{k:_mean([z[k] for z in mod]) for k in ('log_loss','brier')},
                      'multiplicative':{k:_mean([z[k] for z in multi]) for k in ('log_loss','brier')},
                      'power':{k:_mean([z[k] for z in power]) for k in ('log_loss','brier')},
                      'not_proof_of_simultaneous_market_snapshot':True}
    if all('official_jc_integer_line' in x for x in test):
        vals=[];warn=0
        for x in test:
            line=x['official_jc_integer_line'];v=c.score_grid(x['score_matrix'],x['result_score'],line)
            vals.append(v['JC']['log_loss']);warn+=int(v['JC_letdraw_warning']['risk']=='SECOND_REVIEW')
        r['JC']={'status':'OFFICIAL_LINE_BENCHMARK','n':len(test),'mean_log_loss':_mean(vals),
                 'narrow_warning_count':warn,'no_automatic_direction_change':True}
    return r


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input_json',type=Path,help='permitted, prematch-frozen fixture dataset')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    result=run(json.loads(args.input_json.read_text(encoding='utf-8')))
    s=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(s,encoding='utf-8')
    else:print(s)

if __name__=='__main__':main()
