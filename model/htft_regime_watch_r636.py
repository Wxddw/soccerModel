"""Prematch-only HTFT reversal coverage monitor. Research-only read-only diagnostic.

This module uses an already-frozen nine-class HTFT distribution tied to frozen
fulltime score Q. It does NOT predict score margin at halftime, does not fit
weights, and cannot infer future injuries, red cards, penalties or substitutions.
"""
from __future__ import annotations
import math
from joint_tail_calibration_shadow_r636 import grid, aggregates, timestamp, WDL

PATHS=tuple(a+b for a in WDL for b in WDL)
SPECIAL={
    'halftime_lead_lost':('胜平','胜负','负平','负胜'),
    'halftime_lead_reversed':('胜负','负胜'),
    'halftime_trailing_draw':('负平','胜平'),
    'halftime_draw_to_decisive':('平胜','平负'),
    'first_half_draw_held':('平平',),
    'late_home_wins':('平胜','负胜'),
    'late_away_wins':('平负','胜负'),
}


def audit(packet):
    keys={'match_id','source_id','observed_at','cutoff','kickoff',
          'score_matrix','htft_probabilities','published_htft_top2','snapshot_decimal_places'}
    if not isinstance(packet,dict) or set(packet)!=keys:
        raise ValueError('full prematch Q/HTFT exact input only; reject results')
    if not isinstance(packet['match_id'],str) or not packet['match_id']:
        raise ValueError('match id required')
    if not isinstance(packet['source_id'],str) or not packet['source_id']:
        raise ValueError('source id required')
    if not timestamp(packet['observed_at'])<=timestamp(packet['cutoff'])<timestamp(packet['kickoff']):
        raise ValueError('postcutoff HTFT source rejected')
    q=grid(packet['score_matrix'])
    p=packet['htft_probabilities']
    if not isinstance(p,dict) or set(p)!=set(PATHS):
        raise ValueError('all nine paths required')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>1 for v in p.values()):
        raise ValueError('malformed nine-way probability')
    digits=packet['snapshot_decimal_places']
    if digits is None:
        tol=1e-8
    elif type(digits) is int and 3 <= digits <= 10:
        tol=9*.5*10**(-digits)+1e-8
        if any(abs(round(v,digits)-v)>1e-9 for v in p.values()):
            raise ValueError('unrounded HTFT values misrepresented as rounded snapshot')
    else:
        raise ValueError('declared decimal precision must be 3..10 or None')
    if abs(math.fsum(p.values())-1)>tol:raise ValueError('HTFT probability mass not 1')
    ft=aggregates(q)['wdl']
    for w in WDL:
        if abs(math.fsum(p[h+w] for h in WDL)-ft[w])>tol:
            raise ValueError('HTFT fulltime marginal not linked to original Q')
    top=packet['published_htft_top2']
    if not isinstance(top,list) or len(top)!=2 or len(set(top))!=2 or any(x not in PATHS for x in top):
        raise ValueError('exactly two valid HTFT picks required')
    ranked=sorted(PATHS,key=lambda k:(-p[k],PATHS.index(k)))
    if top!=ranked[:2]:
        raise ValueError('published HTFT top2 not aligned with prematch nine-class probabilities')
    result={'status':'RESEARCH_HTFT_MONITOR_ONLY','formal_grant':None,'production_changed':False,
            'match_id':packet['match_id'],'rounded_input_tolerance':tol,'top2_probability_mass':math.fsum(p[k] for k in top),
            'top2':top,'tail_paths':{k:float(p[k]) for k in ('胜负','负胜','胜平','负平','平平','平负')},
            'special_family_probability':{k:math.fsum(p[x] for x in cells) for k,cells in SPECIAL.items()},
            'all_paths':{k:p[k] for k in PATHS},
            'note':'Families overlap; their probabilities must never be summed as independent classes.'}
    return result


def cohort(prematch_audits):
    if not isinstance(prematch_audits,list) or not prematch_audits:
        raise ValueError('nonempty frozen prematch HTFT audit list required')
    seen=set()
    result={'n':len(prematch_audits),'expected_htft_top2_hits':0.,'expected_paths':{k:0. for k in PATHS},
            'expected_special':{k:0. for k in SPECIAL},'research_only':True,'formal_grant':None}
    for p in prematch_audits:
        if p['match_id'] in seen:raise ValueError('duplicate match in cohort')
        seen.add(p['match_id'])
        result['expected_htft_top2_hits']+=p['top2_probability_mass']
        for k in PATHS:result['expected_paths'][k]+=p['all_paths'][k]
        for k in SPECIAL:result['expected_special'][k]+=p['special_family_probability'][k]
    return result
