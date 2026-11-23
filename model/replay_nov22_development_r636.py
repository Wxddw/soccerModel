"""Read-only audit of Nov 22 research Q and later actual results (DEVELOPMENT ONLY).

Use snapshot at its saved hash and run prematch diagnostics before *any* actual
result join; this does NOT train a Nov22 challenger or certify improvements.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from joint_tail_calibration_shadow_r636 import grid, aggregates, score, timestamp
from htft_regime_watch_r636 import audit as htft_audit, cohort as htft_cohort


def digest(payload):
    return sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def preflight(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('research_only') is not True or snapshot.get('model_calibration_verified') is not False:
        raise ValueError('only uncalibrated frozen research snapshots supported')
    if digest({k:v for k,v in snapshot.items() if k!='sha256_pre_hash'})!=snapshot.get('sha256_pre_hash'):
        raise ValueError('original snapshot hash mismatch')
    if snapshot.get('source_odds_per_price_observed_at_verified') is not False:
        raise ValueError('dataset authority status changed unexpectedly')
    observed=snapshot['observed_at_beijing']
    ids=set();out=[];allht=[]
    for m in snapshot['matches']:
        if m['id'] in ids:raise ValueError('duplicate fixture')
        ids.add(m['id'])
        if not timestamp(observed)<timestamp(m['kickoff_beijing']):
            raise ValueError('snapshot captured after fixture kickoff')
        g=grid(m['score_matrix_14x14'])
        a=aggregates(g,m['signed_jc_line'])
        if m['score_top3']!=a['score_top3']:
            raise ValueError('published Score Top3 not faithful to Q')
        if m['goal_top3_bucket_including_7plus']!=a['goal_top3']:
            raise ValueError('published Goal Top3 not faithful to Q')
        h=htft_audit({'match_id':m['id'],'source_id':'20261122-1352-research-market-IPF',
                      'observed_at':observed,'cutoff':observed,'kickoff':m['kickoff_beijing'],
                      'score_matrix':m['score_matrix_14x14'],
                      'htft_probabilities':m['halftime_fulltime_joint'],
                      'published_htft_top2':[m['half_full_main'],m['half_full_backup']],
                      'snapshot_decimal_places':5})
        allht.append(h)
        out.append({'match_id':m['id'],'league':m['league'],'source_kickoff':m['kickoff_beijing'],
                    'original_score_top3_mass':math.fsum(g[score(x)] for x in m['score_top3']),
                    'goal_high5_plus_mass':math.fsum(a['goals'][v] for v in ('5','6','7+')),
                    'goal_low01_mass':a['goals']['0']+a['goals']['1'],
                    'exact_4_mass':a['goals']['4'],
                    'goal_7plus_mass':a['goals']['7+'],
                    'jc_draw_mass':a['jc']['让平'],
                    'htft_top2_mass':h['top2_probability_mass'],
                    'htft_reversal_mass':h['special_family_probability']['halftime_lead_reversed'],
                    'htft_lost_lead_mass':h['special_family_probability']['halftime_lead_lost'],
                    'htft_special':h['special_family_probability'],
                    'frozen_goal_top3':a['goal_top3'],
                    'frozen_score_top3':a['score_top3'],
                    'frozen_htft_top2':h['top2'],
                    'no_challenger_fitted':True})
    return out,htft_cohort(allht)


def evaluate(snapshot,recap):
    prematch,htft=preflight(snapshot)
    if not isinstance(recap,dict) or recap.get('verified_snapshot_sha256')!=snapshot['sha256_pre_hash']:
        raise ValueError('postmatch recap not linked to this exact frozen pregame snapshot')
    if len(recap['results'])!=len(prematch):raise ValueError('incomplete postmatch match join')
    byid={r['id']:r for r in recap['results']}
    if len(byid)!=len(prematch):raise ValueError('duplicate postmatch match ID')
    rows=[];count=Counter();act_ht=Counter();hi5=0
    for p in prematch:
        r=byid.get(p['match_id'])
        if not r:raise ValueError('postmatch fixture missing')
        h,a=score(r['fulltime']);hh,ha=score(r['halftime'])
        if hh>h or ha>a:raise ValueError('halftime cannot exceed normal-time final score')
        ht=('胜' if hh>ha else '平' if hh==ha else '负')+('胜' if h>a else '平' if h==a else '负')
        if r['htft_actual']!=ht:
            raise ValueError('postmatch HTFT mislabeled')
        if r['score_top3_hit']!=(r['fulltime'] in p['frozen_score_top3']):
            raise ValueError('postmatch result inconsistent with frozen Score Top3')
        if r['htft_top2_hit']!=(ht in p['frozen_htft_top2']):
            raise ValueError('postmatch result inconsistent with frozen HTFT Top2')
        goal=h+a;count[goal if goal<=6 else '7+']+=1
        act_ht[ht]+=1
        hi5+=goal>=5
        rows.append({'match_id':p['match_id'],'actual_score':r['fulltime'],
                     'htft_actual':ht,'score_top3_hit':r['score_top3_hit'],
                     'htft_top2_hit':r['htft_top2_hit'],'actual_high5_plus':goal>=5,
                     'prematch_score_top3_mass':p['original_score_top3_mass'],
                     'prematch_goal_high5_plus_mass':p['goal_high5_plus_mass'],
                     'prematch_htft_lost_lead_mass':p['htft_lost_lead_mass']})
    return {'type':'POSTMATCH_DEVELOPMENT_DIAGNOSTICS_NOT_TRAINING','formal_grant':None,
            'production_changed':False,'snapshot_sha256':snapshot['sha256_pre_hash'],
            'eligibility':'uncalibrated-market-IPF-shadow; source odds per-price timestamps not verified',
            'n':len(rows),
            'score_top3_expected_hits':math.fsum(x['original_score_top3_mass'] for x in prematch),
            'score_top3_actual_hits':sum(x['score_top3_hit'] for x in rows),
            'htft_top2_expected_hits':htft['expected_htft_top2_hits'],
            'htft_top2_actual_hits':sum(x['htft_top2_hit'] for x in rows),
            'high5plus_expected_matches':math.fsum(x['goal_high5_plus_mass'] for x in prematch),
            'high5plus_actual_matches':hi5,
            'htft_expected_paths':htft['expected_paths'],
            'htft_actual_paths':dict(act_ht),
            'goals_actual':dict(count),
            'per_match':rows,
            'warning':'Never change fitted parameters after this recap and claim unbiased backtest; no challenger existed before the 2026-11-22 fixtures.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frozen_snapshot');p.add_argument('postmatch_recap');p.add_argument('--output')
    args=p.parse_args()
    s=json.loads(Path(args.frozen_snapshot).read_text(encoding='utf-8'))
    r=json.loads(Path(args.postmatch_recap).read_text(encoding='utf-8'))
    result=evaluate(s,r)
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(txt,encoding='utf-8')
    else:print(txt)

if __name__=='__main__':main()
