"""R6.3.13 optional, conditional HT/FT *research* distribution.

A score H:A from full-time Q is split into half-time goals with binomial
thinning. The input first-half fractions must come from a prematch historical
calibration; the bridge never infers them from full-time final results.
This is a lightweight transition baseline, not a learned temporal hazard model.
"""
from __future__ import annotations
from collections import defaultdict
import math
import candidate_models_r6313 as candidate
import joint_bridge_r6312 as joint

HTFT_ORDER=tuple(h+f for h in joint.WDL for f in joint.WDL)


def _binomial(n:int,q:float)->list[float]:
    return [math.comb(n,i)*q**i*(1-q)**(n-i) for i in range(n+1)]


def aggregate_htft(matrix: list[dict], *,fraction_home:float,fraction_away:float,
                   source_id:str,observed_at:str,kickoff:str)->dict:
    candidate.check_prematch_source(source_id,observed_at,kickoff)
    for p in (fraction_home,fraction_away):
        if type(p) not in (int,float) or not math.isfinite(p) or p<=0 or p>=1:
            raise ValueError('halftime fractions must be finite in (0,1)')
    full=joint.aggregate(matrix)
    htft={x:0. for x in HTFT_ORDER}
    htw={k:0. for k in joint.WDL}
    ftw={k:0. for k in joint.WDL}
    for row in matrix:
        h,a=joint.parse_score(row['score']);p=row['probability']
        ft=joint.wdl_label(h,a)
        hb=_binomial(h,float(fraction_home));ab=_binomial(a,float(fraction_away))
        for hi,vh in enumerate(hb):
            for ai,va in enumerate(ab):
                w=joint.wdl_label(hi,ai);v=p*vh*va
                htft[w+ft]+=v;htw[w]+=v;ftw[ft]+=v
    if max(abs(ftw[k]-full['wdl_probabilities'][k]) for k in joint.WDL)>1e-9:
        raise AssertionError('FT marginal no longer matches source score matrix')
    if abs(math.fsum(htft.values())-1)>1e-9:raise AssertionError('HTFT does not conserve mass')
    ranked=sorted(HTFT_ORDER,key=lambda x:(-htft[x],HTFT_ORDER.index(x)))
    return {'status':'RESEARCH_HTFT_LINKED','method':'conditional_binomial_thinning',
            'probabilities':htft,'first_half_wdl':htw,'full_time_wdl':ftw,
            'top3':ranked[:3],'sum':math.fsum(htft.values()),'source_id':source_id,
            'fraction_home':fraction_home,'fraction_away':fraction_away,
            'observed_at':observed_at,'kickoff':kickoff,'research_only':True,
            'formal_halftime_selection_grant':None,
            'note':'Conditional thinning is a baseline; must be validated against real HT data.'}
