"""Nov24 R6.3.6 shadow: static market discrepancy and near-tie coverage review.
Never modify Q, original picks, production, or assert bookmaker intent.
Thresholds are research hypotheses fixed for subsequent independent tests.
"""
from __future__ import annotations
from math import fsum, isfinite
from copy import deepcopy
from matchday_publish_gate_r636 import _dt, WDL, GOALS
from r636_exposure_guards_20261122 import _distinct_family_source_pairs

VERSION='R636_20261124_SELECTION_RISK_SHADOW'
JC=('让胜','让平','让负')
FAMILIES={'roster','tactics','schedule','motivation','weather'}

def normalized(odds):
    if not isinstance(odds,(list,tuple)) or len(odds)<2 or any(type(x) not in (float,int) or not isfinite(x) or x<=1 for x in odds):
        raise ValueError('decimal odds required')
    w=[1/x for x in odds]; z=fsum(w)
    return [p/z for p in w]

def _probs(p, labels):
    if not isinstance(p,dict) or set(p)!=set(labels) or any(type(x) not in (float,int) or not isfinite(x) or not 0<=x<=1 for x in p.values()) or abs(fsum(p.values())-1)>1e-8:
        raise ValueError('complete normalized probability distribution required')
    return p

def rank(p, labels):
    return sorted(labels,key=lambda k:(-p[k],labels.index(k)))

def _pair(pair, labels, first=None):
    if not isinstance(pair,list) or len(pair)!=2 or len(set(pair))!=2 or any(x not in labels for x in pair) or (first is not None and pair[0]!=first):
        raise ValueError('ordered two distinct candidates required')
    return pair

def static_market_review(*, cutoff, kickoff, jc_wdl, eu_wdl, ah_home, crowd=None, observations):
    """Only a static comparison of observed prices; no claim about prior movements.
    observations: per input record {source_id,observed_at}, time at which the
    value was actually seen. Caller must verify provenance, not invent timestamps.
    """
    c,k=_dt(cutoff),_dt(kickoff)
    if c>=k: raise ValueError('prematch cutoff required')
    vals={'jc_wdl':jc_wdl,'eu_wdl':eu_wdl,'ah_home':ah_home,'crowd':crowd}
    if set(observations)!={a for a,v in vals.items() if v is not None}: raise ValueError('explicit provenance for every available input')
    for x in observations.values():
        if not isinstance(x,dict) or set(x)!={'source_id','observed_at'} or not isinstance(x['source_id'],str) or not x['source_id'].strip() or _dt(x['observed_at'])>c: raise ValueError('missing or postcutoff market observation')
    if ah_home is not None and (type(ah_home) not in (int,float) or not isfinite(ah_home) or abs(ah_home)>7 or abs(4*ah_home-round(4*ah_home))>1e-9): raise ValueError('Asian quarter line, not JC integer')
    if any(v is not None and (not isinstance(v,(list,tuple)) or len(v)!=3) for v in (jc_wdl,eu_wdl)):raise ValueError('three 1X2 odds required')
    jp=None if jc_wdl is None else _probs(dict(zip(WDL,normalized(jc_wdl))),WDL)
    ep=None if eu_wdl is None else _probs(dict(zip(WDL,normalized(eu_wdl))),WDL)
    if crowd is not None: _probs(crowd,WDL)
    flags=[]; detail={}; fav=None
    if jp is not None:
        fav=max(('胜','负'),key=lambda z:jp[z]); detail['favorite']=fav
        if ep is not None and abs((_dt(observations['jc_wdl']['observed_at'])-_dt(observations['eu_wdl']['observed_at'])).total_seconds())<=3600:
            # Explicitly cross-market, not a time-series direction. Both are one family.
            diff=jp[fav]-ep[fav]; detail['jc_minus_eu_favorite_pp']=100*diff
            if diff>=.07: flags.append('JC_EU_FAVORITE_PREMIUM_REVIEW')
            if fav=='负' and jp[fav]>=.48 and diff>=.05 and abs(jp['胜']-jp['平'])<=.03:
                flags.append('AWAY_FAVORITE_PROTECTION_FRAGILE_REVIEW')
            if ah_home is not None and abs((_dt(observations['jc_wdl']['observed_at'])-_dt(observations['ah_home']['observed_at'])).total_seconds())<=3600:
                burden=-ah_home if fav=='胜' else ah_home
                detail['favorite_asian_burden']=burden
                if jp[fav]>=.48 and diff>=.07 and burden<=.5:
                    flags.append('MID_FAVORITE_CROSS_MARKET_SHALLOW_REVIEW')
        if crowd is not None and abs((_dt(observations['jc_wdl']['observed_at'])-_dt(observations['crowd']['observed_at'])).total_seconds())<=3600:
            excess=crowd['平']-jp['平']; detail['draw_buy_excess_pp']=100*excess
            if excess>=.08: flags.append('DRAW_BUY_EXCESS_REVIEW')
    return {'version':VERSION,'flags':flags,'features':detail,'market_family_count':1 if observations else 0,
            'intent_proven':False,'movement_verified':False,'status':'STATIC_ONLY' if jp is not None else 'REGULAR_MARKET_UNAVAILABLE',
            'auto_flip':False}

def _support(evidence,cutoff):
    """Facts must be specific to target outcome/tail, not generic adverse news."""
    if not isinstance(evidence,list):raise ValueError('evidence list required')
    groups={}
    for e in evidence:
        if not isinstance(e,dict) or set(e)!={'family','source_id','observed_at','target'} or e['family'] not in FAMILIES or not isinstance(e['source_id'],str) or not e['source_id'].strip() or _dt(e['observed_at'])>cutoff or e['target'] not in ('胜','平','负','让平','high','low'):
            raise ValueError('invalid/postcutoff target-specific nonmarket evidence')
        groups.setdefault(e['target'],set()).add((e['family'],e['source_id']))
    return {k:_distinct_family_source_pairs(v) for k,v in groups.items()}

def coverage_review(*, cutoff, kickoff, wdl, jc, goals, official_jc_line, regular_open,
                    wdl_pair, jc_pair, goal_top3, score_top3, htft=None, market_flags=(), evidence=None):
    """Same-Q input required in live integration. Candidate alternatives are separate
    selection-policy experiments (not probability rank or production picks).
    """
    c,k=_dt(cutoff),_dt(kickoff)
    if c>=k:raise ValueError('cutoff precedes kickoff')
    if type(regular_open) is not bool or type(official_jc_line) is not int:raise ValueError('verified availability and integer JC line required')
    p=_probs(wdl,WDL); j=_probs(jc,JC); g=_probs(goals,GOALS)
    if regular_open: _pair(wdl_pair,WDL)
    elif wdl_pair is not None:raise ValueError('unavailable regular market cannot publish picks')
    _pair(jc_pair,JC)
    if not isinstance(goal_top3,list) or len(goal_top3)!=3 or len(set(goal_top3))!=3 or any(x not in GOALS for x in goal_top3):raise ValueError('goal Top3 required')
    if not isinstance(score_top3,list) or len(score_top3)!=3 or len(set(score_top3))!=3:raise ValueError('score Top3 required')
    margins=[]
    for s in score_top3:
        h,a=map(int,s.split(':'))
        if min(h,a)<0:raise ValueError('invalid score')
        margins.append(h-a)
    supp=_support([] if evidence is None else evidence,c)
    r=rank(p,WDL); jr=rank(j,JC); gr=rank(g,GOALS)
    flags=[]; alternatives={}; metrics={'wdl_second_third_gap':p[r[1]]-p[r[2]],'jc_first_second_gap':j[jr[0]]-j[jr[1]],'letdraw_probability':j['让平'],'letdraw_margin':-official_jc_line,'letdraw_score_top3_count':margins.count(-official_jc_line),'high_tail_mass':sum(g[z] for z in ('5','6','7+')),'low_tail_mass':g['0']+g['1']}
    if regular_open:
        if p[r[1]]-p[r[2]]<=.03:flags.append('WDL_PROTECTION_CUTOFF_NEAR_TIE')
        if r[0]=='负' and p[r[0]]>=.48 and p[r[1]]-p[r[2]]<=.03:
            flags.append('AWAY_FAVORITE_NARROW_PROTECTION_REVIEW')
            if wdl_pair==['负','平'] and 'AWAY_FAVORITE_PROTECTION_FRAGILE_REVIEW' in market_flags and supp.get('胜',0)>=2:
                alternatives['wdl_pair']=['负','胜']
        if wdl_pair==r[:2] and '平' not in wdl_pair and 0<=p[wdl_pair[1]]-p['平']<=.03:
            flags.append('DRAW_PROTECTION_REVIEW')
            if set(market_flags)&{'DRAW_BUY_EXCESS_REVIEW','MID_FAVORITE_CROSS_MARKET_SHALLOW_REVIEW'} and supp.get('平',0)>=2 and wdl_pair[0]!='平':
                alternatives['wdl_pair']=[wdl_pair[0],'平']
    if j[jr[0]]-j[jr[1]]<=.05: flags.append('JC_TOP_TWO_NARROW_REVIEW')
    if abs(official_jc_line)>=2 and '让平' not in jc_pair and (j[jr[0]]-j[jr[1]]<=.05 or metrics['letdraw_score_top3_count']>=1):flags.append('DEEP_JC_EXACT_MARGIN_PROTECTION_REVIEW')
    if jc_pair==jr[:2] and '让平' not in jc_pair and 0<=j[jc_pair[1]]-j['让平']<=.03:
        flags.append('LETDRAW_SECOND_SLOT_NEAR_TIE')
        if supp.get('让平',0)>=2 and jc_pair[0]!='让平':alternatives['jc_pair']=[jc_pair[0],'让平']
    high=[x for x in gr if x in ('5','6','7+') and x not in goal_top3]
    low=[x for x in gr if x in ('0','1') and x not in goal_top3]
    if not any(x in ('5','6','7+') for x in goal_top3):flags.append('HIGH_TAIL_ABSENT_FROM_TOP3')
    if not any(x in ('0','1') for x in goal_top3):flags.append('LOW_TAIL_ABSENT_FROM_TOP3')
    for label,buckets in [('high',high),('low',low)]:
        if buckets:
            z=buckets[0]; gap=g[goal_top3[-1]]-g[z]; metrics[label+'_best_excluded']=z; metrics[label+'_slot_gap']=gap
            if gap<=.025:flags.append(label.upper()+'_TAIL_NEAR_THIRD_SLOT')
            if goal_top3==gr[:3] and 0<=gap<=.025 and supp.get(label,0)>=2 and supp.get('low' if label=='high' else 'high',0)<2:
                alternatives['goal_top3']=goal_top3[:2]+[z] # at most one slot; retain Top2
    if supp.get('high',0)>=2 and supp.get('low',0)>=2:flags.append('CONFLICTING_TAIL_EVIDENCE_NO_SWAP')
    if htft is not None:
        from matchday_publish_gate_r636 import HTFT
        h=_probs(htft,HTFT)
        if any(abs(fsum(h[a+b] for a in WDL)-p[b])>1e-8 for b in WDL):raise ValueError('HTFT Q marginal mismatch')
        hr=rank(h,HTFT); metrics['htft_second_third_gap']=h[hr[1]]-h[hr[2]];metrics['htft_draw_final_mass']=fsum(h[a+'平'] for a in WDL)
        if h[hr[1]]-h[hr[2]]<=.03:flags.append('HTFT_BACKUP_NEAR_TIE_REVIEW')
    else:flags.append('HTFT_NINE_CLASS_MISSING_NO_CALIBRATION')
    return {'version':VERSION,'flags':flags,'metrics':metrics,'independent_target_evidence_counts':supp,'shadow_alternatives':alternatives,'original_wdl_pair':deepcopy(wdl_pair),'original_jc_pair':deepcopy(jc_pair),'original_goal_top3':list(goal_top3),'production_mutated':False,'auto_flip':False,'formal_grant':None}

def review_with_original_q(packet, market_packet, *, regular_open, wdl_pair, jc_pair, static_packet=None, evidence=None, tail_evidence=None, aic_records=None):
    from market_trap_integration_r636 import prematch_audit_with_market
    old=prematch_audit_with_market(packet,market_packet,tail_evidence=tail_evidence,aic_records=aic_records)
    exp=old['existing_exposure']
    if static_packet is not None and (static_packet['cutoff']!=packet['cutoff'] or static_packet['kickoff']!=packet['kickoff']):raise ValueError('static market time mismatch')
    static=None if static_packet is None else static_market_review(**static_packet)
    jc=exp['jc_exact_margin']; line=packet['official_jc_line']
    if line is None:raise ValueError('official JC line missing')
    from matchday_publish_gate_r636 import review
    x=review(packet)
    # refuse mismatched published Top3 for live selection-policy challenger
    if regular_open and (not wdl_pair or wdl_pair[0]!=packet['frozen_wdl']):raise ValueError('published WDL single/pair mismatch')
    if x['score_top3_derived']!=packet['published_score_top3'] or x['goal_top3_derived']!=packet['published_goal_top3']:raise ValueError('original cross-layer ranking mismatch')
    a=coverage_review(cutoff=packet['cutoff'],kickoff=packet['kickoff'],wdl=x['wdl'],jc=x['jc'],goals=x['goal_buckets'],official_jc_line=line,regular_open=regular_open,wdl_pair=wdl_pair,jc_pair=jc_pair,goal_top3=packet['published_goal_top3'],score_top3=packet['published_score_top3'],htft=packet['htft_probabilities'],market_flags=[] if static is None else static['flags'],evidence=evidence)
    return {'existing_audit':old,'static_market':static,'selection_research':a,'formal_grant':None,'production_mutated':False}