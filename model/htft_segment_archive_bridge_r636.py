"""Read-only bridge for 31x31 archived Q to TimeSeg v0.1 0..10 engine.

Conserve ALL original Q cell mass. Cells with h>10 or a>10 are handled
analytically by a *neutral conditional binomial timing fallback*, without
pretending to estimate dynamic hazards in that extreme tail.

This bridge is research only. For every nine-class HTFT probability the
worst-case difference between a hypothetical dynamic-tail model and the
neutral fallback is bounded by the *declared* tail mass.
"""
from __future__ import annotations
import math
from htft_segment_hazard_r636 import predict as predict_supported, _wdl, PHASES, PATHS

MAX_APPROX_TAIL_MASS = .001  # safety only; NOT a statistically fitted threshold


def predict_archived_grid(full_grid, spec):
    if (not isinstance(full_grid, list) or not 1 <= len(full_grid) <= 31
        or any(not isinstance(row, list) or len(row) != len(full_grid)
               for row in full_grid)):
        raise ValueError('square complete Q grid of at most 31x31 required')
    q_small=[]; tail=[]; total=0.; keep=0.
    for h,row in enumerate(full_grid):
        for a,p in enumerate(row):
            if type(p) not in (int,float) or not math.isfinite(p) or p<0 or p>1:
                raise ValueError('each Q cell must be finite, nonnegative and <=1')
            total+=p
            if h<=10 and a<=10:
                q_small.append({'score':f'{h}:{a}','probability':float(p)})
                keep+=p
            else:
                tail.append((h,a,float(p)))
    if abs(total-1)>1e-8 or keep<1e-7:
        raise ValueError('incomplete full Q or no usable dynamic mass')
    tail_mass=math.fsum(p for _,_,p in tail)
    if tail_mass > MAX_APPROX_TAIL_MASS:
        raise ValueError('archived score tail exceeds preregistered approximation guard')
    supported=predict_supported(
        [{'score':x['score'],'probability':x['probability']/keep} for x in q_small],spec)
    result={k:keep*v for k,v in supported['probabilities'].items()}
    home=[keep*s['home_expected_goals'] for s in supported['segments']]
    away=[keep*s['away_expected_goals'] for s in supported['segments']]
    fh=math.fsum(spec['home_shares'][:3])
    fa=math.fsum(spec['away_shares'][:3])
    for h,a,p in tail:
        if p==0: continue
        ft=_wdl(h,a)
        for i in range(h+1):
            ph=math.comb(h,i)*fh**i*(1-fh)**(h-i)
            for j in range(a+1):
                pa=math.comb(a,j)*fa**j*(1-fa)**(a-j)
                result[_wdl(i,j)+ft]+=p*ph*pa
        for t in range(6):
            home[t]+=p*h*spec['home_shares'][t]
            away[t]+=p*a*spec['away_shares'][t]
    if abs(math.fsum(result.values())-1)>1e-8:
        raise AssertionError('archive-to-segment mass conservation failed')
    for label in ('胜','平','负'):
        src=math.fsum(full_grid[h][a] for h in range(len(full_grid))
                      for a in range(len(full_grid)) if _wdl(h,a)==label)
        tgt=math.fsum(result[half+label] for half in ('胜','平','负'))
        if abs(src-tgt)>1e-8:
            raise AssertionError('frozen fulltime WDL marginal changed')
    if abs(math.fsum(home)-math.fsum(h*p for h,row in enumerate(full_grid) for p in row))>1e-8:
        raise AssertionError('home time expectations do not sum to frozen Q')
    if abs(math.fsum(away)-math.fsum(a*row[a] for row in full_grid for a in range(len(row))))>1e-8:
        raise AssertionError('away time expectations do not sum to frozen Q')
    ranked=sorted(PATHS,key=lambda k:(-result[k],PATHS.index(k)))
    return {'status':'RESEARCH_NEUTRAL_HIGH_SCORE_TAIL_FALLBACK',
            'research_only':True,'formal_grant':None,'production_changed':False,
            'full_q_mass':total,'dynamic_0_to_10_mass':keep,
            'neutral_tail_fallback_mass':tail_mass,
            'per_class_absolute_dynamic_tail_uncertainty_upper_bound':tail_mass,
            'probabilities':result,'top1':ranked[0],'top2':ranked[:2],
            'top3':ranked[:3],
            'segments':[{'period':PHASES[t],'home_expected_goals':home[t],
                         'away_expected_goals':away[t]} for t in range(6)],
            'note':'No Q tail mass discarded. Dynamic hazards NOT evaluated for >10 score cells.'}
