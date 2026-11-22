"""Audits a REAL previously frozen market/IPF snapshot, without changing it.

Uses only match fields from the archived pregame JSON for the preflight stage.
A separately supplied *postmatch* recap is read AFTER all preflight outputs; no
actual result can enter an individual forecast or time-segment parameter.
No code here was frozen before the 2026-11-21 kickoffs; research only.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
from matchday_publish_gate_r636 import HTFT, WDL
from r636_exposure_guards_20261122 import prematch_exposure_review,batch_exposure_review

ARCHIVED_MATCH_FIELDS = frozenset({
    'id','league','match_local_time_beijing','home','away','official_jc_signed_line',
    'regular_sp_prices','handicap_sp_prices','market_implied_wdl','market_implied_jc',
    'score_probability_grid_18x18','main_selection_research','protect_selection_research',
    'jc_selection_research','jc_protect_research','goal_top3','score_top3',
    'htft_candidates','research_only'})
ARCHIVED_TOP_FIELDS = frozenset({
    'schema','created_at_beijing','fixture_sale_date','source_url','source_capture_method',
    'source_snapshot_third_party_timestamp_verified','market_betting_availability_to_check_at_checkout',
    'model','model_prior_validated','full_M79_production_recreated','formal_grant',
    'frozen_after_development_of_model','matches','snapshot_sha256'})


def digest(d):
    return sha256(json.dumps(d, sort_keys=True, ensure_ascii=False,
                             separators=(',',':'), allow_nan=False).encode('utf8')).hexdigest()


def _wdl(h,a):return '胜' if h>a else '平' if h==a else '负'


def neutral_htft(q, frac=.45):
    """The original 45%-split baseline, NOT an upgraded 6-stage predictor."""
    out={k:0. for k in HTFT}
    for h,row in enumerate(q):
        for a,pr in enumerate(row):
            if pr<=0:continue
            ft=_wdl(h,a)
            for i in range(h+1):
                ph=math.comb(h,i)*frac**i*(1-frac)**(h-i)
                for j in range(a+1):
                    pa=math.comb(a,j)*frac**j*(1-frac)**(a-j)
                    out[_wdl(i,j)+ft]+=pr*ph*pa
    return out


def adapt_archived_market_match(snapshot, m):
    """Explicit bridge: source observed time is *archive creation*, not vendor proof."""
    if not isinstance(m,dict) or set(m) != ARCHIVED_MATCH_FIELDS:
        raise ValueError('archive match fields changed; postmatch contamination prohibited')
    source_time=snapshot['created_at_beijing']
    q=m['score_probability_grid_18x18']
    if len(q)!=18 or any(not isinstance(row,list) or len(row)!=18 for row in q):
        raise ValueError('expected original full 18x18 archive Q')
    cells=[{'score':f'{h}:{a}','probability':p} for h,row in enumerate(q) for a,p in enumerate(row)]
    return {'match_id':m['id'],'kickoff':m['match_local_time_beijing'],
       'cutoff':source_time,
       'q_observation':{'source_id':'local-archive-market-ipf-not-vendor-timestamp','observed_at':source_time},
       'score_grid':cells,
       'frozen_wdl':m['main_selection_research'],
       'published_score_top3':m['score_top3'].split('/'),
       'published_goal_top3':m['goal_top3'].split('/'),
       'published_htft':m['htft_candidates'].split('/'),
       'htft_probabilities':neutral_htft(q),
       'official_jc_line':m['official_jc_signed_line'],
       'jc_observation':{'source_id':'archive-signed-JC-line-not-independent-proof','observed_at':source_time},
       'evidence':[], 'market_home_buy_share':None,'market_buy_observation':None,
       'publication_observation':{'source_id':'archived-published-picks','observed_at':source_time},
       'reversal_proposal':None,'reversal_policy':None}


def run(snapshot, postmatch=None):
    if not isinstance(snapshot,dict) or snapshot.get('schema')!='M79_SHADOW_20261121_MARKET_POISSON_PREMATCH_RESEARCH_V1':
        raise ValueError('expected original 20261121 archived research snapshot')
    if set(snapshot) != ARCHIVED_TOP_FIELDS:
        raise ValueError('archive top-level fields changed, possible leakage')
    if digest({k:v for k,v in snapshot.items() if k!='snapshot_sha256'})!=snapshot.get('snapshot_sha256'):
        raise ValueError('archive integrity sha256 mismatch')
    if not isinstance(snapshot.get('matches'),list) or len(snapshot['matches'])!=18:
        raise ValueError('complete 18 match dataset required')
    # Stage 1: prematch decisions and probabilities only, never actual results.
    reviews=[prematch_exposure_review(adapt_archived_market_match(snapshot,m)) for m in snapshot['matches']]
    batch=batch_exposure_review(reviews)
    results={'version':'R636_NOV22_HISTORIC_PREMATCH_QA_RETROSPECTIVE',
             'source_sha256':snapshot['snapshot_sha256'],
             'archive_created_at':snapshot['created_at_beijing'],
             'model':'market-ipf-shadow-not-full-M79-production',
             'archive_provider_price_timestamps_verified':False,
             'n_prematch':len(reviews),'formal_grant':None,
             'weights_fitted_on_this_batch':False,
             'forward_validation_of_nov22_new_model':False,
             'batch_prematch_exposure':batch,
             'count_gates':{k:sum(r['original_component_release_gates'][k]=='SHADOW_CONSISTENT' for r in reviews)
                            for k in ('Outcome','JC','Goal','Score','HTFT')},
             'match_reviews':[{k:r[k] for k in ('match_id','original_prematch_packet_sha256',
                'original_wdl_selection_unchanged','goal_families',
                'goal_tail_evidence','jc_exact_margin','htft_state_distribution',
                'original_component_release_gates','warnings')} for r in reviews]}
    # Stage 2: score *only*, after stage 1 is wholly finished.
    if postmatch is not None:
        if not isinstance(postmatch,dict) or postmatch.get('schema')!='NOV21_PREMATCH_FROZEN_VS_POSTMATCH_AUDIT':
            raise ValueError('expected archived retrospective result audit')
        if postmatch.get('snapshot_sha256_stored')!=snapshot['snapshot_sha256'] or not postmatch.get('sha256_matches'):
            raise ValueError('postmatch attribution or checksum mismatch')
        actual=postmatch.get('rows')
        if not isinstance(actual,list) or len(actual)!=len(reviews) or set(r['id'] for r in actual)!=set(r['match_id'] for r in reviews):
            raise ValueError('postmatch cohort does not match frozen prematch slate')
        count_ht=Counter(r['htft_actual'] for r in actual)
        count_goals=Counter(r['goal_actual'] for r in actual)
        counts={k:sum(r[k] for r in actual) for k in ('regular_hit','protection_hit','jc_hit','goal_top3_hit',
             'goal_top2_hit','score_top3_hit','htft_top1_hit','htft_top2_hit')}
        results['postmatch_descriptive_only']={
            'source':'previous stored independent postmatch recap (not feature input)',
            'n':len(actual),'actual_HTFT_counts':dict(count_ht),
            'actual_goals_0_6_7plus':dict(count_goals),
            'actual_wdl_counts':dict(Counter(r['regular_actual'] for r in actual)),
            'published_frozen_hits':counts,
            'frozen_baseline_proper_scores':postmatch['proper_scores'],
            'new_model_logloss_brier_or_hit_rates':None,
            'nov22_new_model_independent_holdout_n':0}
    return results


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('snapshot');a.add_argument('--postmatch');a.add_argument('--output')
    args=a.parse_args()
    s=json.loads(Path(args.snapshot).read_text(encoding='utf8'))
    post=json.loads(Path(args.postmatch).read_text(encoding='utf8')) if args.postmatch else None
    out=run(s,post)
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(txt,encoding='utf8')
    else:print(txt)
if __name__=='__main__':main()