"""R6.3.13 independent *market benchmark*, no model probability injection.

Own small implementation of multiplicative and power no-vig methods; do not
copy third-party source and do not assume bookmaker price is ground truth.
"""
from __future__ import annotations
import math
import candidate_models_r6313 as candidate
import joint_bridge_r6312 as joint


def devig(snapshot:dict, model_wdl:dict|None=None)->dict:
    if not isinstance(snapshot,dict):raise ValueError('market snapshot must be object')
    needed={'odds','source_id','observed_at','kickoff','market_type'}
    if set(snapshot)!=needed:raise ValueError('market snapshot must have exactly odds/source/time/type')
    if snapshot['market_type']!='WDL_DECIMAL':raise ValueError('only three-way decimal WDL odds supported')
    candidate.check_prematch_source(snapshot['source_id'],snapshot['observed_at'],snapshot['kickoff'])
    o=snapshot['odds']
    if not isinstance(o,dict) or set(o)!=set(joint.WDL):raise ValueError('must give full 1X2 odds')
    if any(type(o[k]) not in (int,float) or not math.isfinite(o[k]) or o[k]<=1 for k in joint.WDL):
        raise ValueError('decimal odds must be finite and >1')
    raw={k:1/float(o[k]) for k in joint.WDL}
    gross=math.fsum(raw.values())
    mul={k:raw[k]/gross for k in joint.WDL}
    # Solve sum((1/odds_i)^k)=1; k=1 at exactly no vig.
    lo,hi=1e-8,64.
    for _ in range(160):
        mid=(lo+hi)/2
        if math.fsum(x**mid for x in raw.values())>1:lo=mid
        else:hi=mid
    expo=(lo+hi)/2
    pw={k:raw[k]**expo for k in joint.WDL}
    sp=math.fsum(pw.values());pw={k:p/sp for k,p in pw.items()}
    diff=None
    if model_wdl is not None:
        if set(model_wdl)!=set(joint.WDL) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in model_wdl.values()) or abs(math.fsum(model_wdl.values())-1)>1e-6:
            raise ValueError('model WDL must sum to one')
        diff={k:float(model_wdl[k])-mul[k] for k in joint.WDL}
    return {'status':'READ_ONLY_MARKET_BENCHMARK',
            'overround':gross-1,'underround':gross<1-1e-6,
            'multiplicative':mul,'power':pw,'power_exponent':expo,
            'max_method_disagreement':max(abs(mul[k]-pw[k]) for k in joint.WDL),
            'model_minus_multiplicative':diff,
            'source_id':snapshot['source_id'],'observed_at':snapshot['observed_at'],
            'market_type':snapshot['market_type'],'research_only':True,
            'moves_production_probabilities':False,
            'note':'WDL decimal quotes only, not JC handicap or Asian push/quarter settlement.'}
