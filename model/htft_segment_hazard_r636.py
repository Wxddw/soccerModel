"""R6.3.6 HTFT six-segment prematch hazard bridge (Shadow only).

Six phases: 0-15, 16-30, 31-45+, 46-60, 61-75, 76-90+.
A discrete piecewise-constant Poisson process uses only prematch-calibrated
segment shares and lead/trail hazard multipliers. It is CONDITIONED back
onto frozen Q(H,A), per terminal score, never altering the original score grid.
This is not a minute-resolved simulator or proven predictive improvement.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import math

PHASES = ('00-15', '16-30', '31-45+', '46-60', '61-75', '76-90+')
WDL = ('胜', '平', '负')
PATHS = tuple(h + f for h in WDL for f in WDL)
FACTOR_KEYS = ('home_leading','home_trailing','away_leading','away_trailing')


def _time(s):
    if not isinstance(s, str): raise ValueError('timezone-aware timestamp required')
    try: dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError as e: raise ValueError('bad timestamp') from e
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('naive timestamp blocked')
    return dt


def _score(s):
    if not isinstance(s,str) or ':' not in s: raise ValueError('score H:A required')
    bits=s.split(':')
    if len(bits)!=2 or any(not z.isdigit() or str(int(z))!=z for z in bits):
        raise ValueError('canonical nonnegative H:A required')
    h,a=(int(z) for z in bits)
    if h>10 or a>10:raise ValueError('score beyond certified 0..10 grid')
    return h,a


def _wdl(h,a):
    return '胜' if h>a else '平' if h==a else '负'


def _prob_grid(q):
    if not isinstance(q,list) or not q:raise ValueError('complete prematch Q grid required')
    grid={}
    for row in q:
        if not isinstance(row,dict) or set(row)!={'score','probability'}:
            raise ValueError('unexpected or missing prematch grid field')
        key=_score(row['score']);p=row['probability']
        if key in grid or type(p) not in (float,int) or not math.isfinite(p) or not 0<=p<=1:
            raise ValueError('bad or duplicate Q cell')
        grid[key]=float(p)
    if not math.isclose(math.fsum(grid.values()),1.,abs_tol=1e-8,rel_tol=0):
        raise ValueError('incomplete Q mass; no silent normalization')
    return grid


def _shares(xs):
    if not isinstance(xs,(list,tuple)) or len(xs)!=6 or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in xs):
        raise ValueError('exactly six strictly positive finite period weights required')
    if not math.isclose(math.fsum(xs),1.,abs_tol=1e-8,rel_tol=0):
        raise ValueError('six period shares must sum to one')
    return tuple(float(x) for x in xs)


def _factors(f):
    if not isinstance(f,dict) or set(f)!=set(FACTOR_KEYS):
        raise ValueError('four explicit lead/trail factors required')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not .5<=v<=1.8 for v in f.values()):
        raise ValueError('unvalidated lead/trail hazard factor')
    return {k:float(f[k]) for k in FACTOR_KEYS}


def _poisson_bounded(lam,max_n):
    p=math.exp(-lam);arr=[p]
    for j in range(1,max_n+1):
        p=p*lam/j;arr.append(p)
    return arr


def _check_spec(s):
    keys={'source_id','observed_at','cutoff','kickoff','home_xg','away_xg','home_shares',
          'away_shares','state_factors','latest_training_result_observed_at','calibration_id'}
    if not isinstance(s,dict) or set(s)!=keys:
        raise ValueError('complete explicit prematch temporal spec required')
    for k in ('source_id','calibration_id'):
        if not isinstance(s[k],str) or not s[k].strip():raise ValueError('nonempty source ids required')
    if not _time(s['latest_training_result_observed_at'])<=_time(s['observed_at'])<=_time(s['cutoff'])<_time(s['kickoff']):
        raise ValueError('training result or source not available before kickoff cutoff')
    for x in (s['home_xg'],s['away_xg']):
        if type(x) not in (int,float) or not math.isfinite(x) or not 0<x<=6:
            raise ValueError('prematch xG must be independently sourced, finite (0,6]')
    return _shares(s['home_shares']),_shares(s['away_shares']),_factors(s['state_factors'])


def predict(q, spec):
    """Predict nine HTFT paths and conditional expected goals per period.

    Each FT cell Q(H,A) is frozen: model only reallocates its temporal paths.
    
    State dependence is evaluated at *segment boundaries*, not within a segment.
    No observed match events or actual scores can enter this function.
    """
    wh,wa,factors=_check_spec(spec)
    grid=_prob_grid(q)
    max_h=max(h for h,a in grid if grid[h,a]>0)
    max_a=max(a for h,a in grid if grid[h,a]>0)
    # [probability, home_period0..5 weighted sums, away_period0..5 weighted sums]
    states={(0,0,''):[1.]+[0.]*12}
    for stage in range(6):
        next_states=defaultdict(lambda:[0.]*13)
        for (h,a,ht),carry in states.items():
            diff=h-a
            mh=factors['home_leading'] if diff>0 else factors['home_trailing'] if diff<0 else 1.
            ma=factors['away_trailing'] if diff>0 else factors['away_leading'] if diff<0 else 1.
            ph=_poisson_bounded(float(spec['home_xg'])*wh[stage]*mh,max_h-h)
            pa=_poisson_bounded(float(spec['away_xg'])*wa[stage]*ma,max_a-a)
            for dh,hp in enumerate(ph):
                for da,ap in enumerate(pa):
                    p=hp*ap
                    if p==0.:continue
                    hh,aa=h+dh,a+da
                    next_ht=_wdl(hh,aa) if stage==2 else ht
                    state=next_states[(hh,aa,next_ht)]
                    w=p*carry[0]
                    state[0]+=w
                    for j in range(stage):
                        state[1+j]+=p*carry[1+j]
                        state[7+j]+=p*carry[7+j]
                    state[1+stage]+=w*dh
                    state[7+stage]+=w*da
        states=next_states
    terminal=defaultdict(float)
    for (h,a,ht),v in states.items():terminal[h,a]+=v[0]
    out={k:0. for k in PATHS}
    period_h=[0.]*6;period_a=[0.]*6
    ht_wdl={k:0. for k in WDL};ft_wdl={k:0. for k in WDL}
    for (h,a,ht),v in states.items():
        final_mass=terminal[h,a]
        if final_mass<=0:continue
        scale=grid.get((h,a),0.)/final_mass
        p=v[0]*scale
        out[ht+_wdl(h,a)]+=p
        ht_wdl[ht]+=p;ft_wdl[_wdl(h,a)]+=p
        for j in range(6):
            period_h[j]+=v[1+j]*scale
            period_a[j]+=v[7+j]*scale
    for (h,a),prob in grid.items():
        if prob>0 and terminal[h,a]<=1e-280:
            raise ValueError('frozen Q score has no numerically usable temporal path')
    if not math.isclose(math.fsum(out.values()),1.,abs_tol=1e-8,rel_tol=0):
        raise AssertionError('nine-way HTFT probability conservation failed')
    for k in WDL:
        truth=math.fsum(v for (h,a),v in grid.items() if _wdl(h,a)==k)
        if abs(ft_wdl[k]-truth)>1e-8:raise AssertionError('frozen fulltime WDL mismatch')
    if abs(math.fsum(period_h)-math.fsum(h*p for (h,a),p in grid.items()))>1e-8:
        raise AssertionError('home period expected goals do not add to FT expectation')
    if abs(math.fsum(period_a)-math.fsum(a*p for (h,a),p in grid.items()))>1e-8:
        raise AssertionError('away period expected goals do not add to FT expectation')
    ranked=sorted(PATHS,key=lambda k:(-out[k],PATHS.index(k)))
    return {'version':'HTFT_TIMESEG_V0.1_SHADOW','research_only':True,'formal_grant':None,
            'production_changed':False,'prematch_cutoff':spec['cutoff'],'source_id':spec['source_id'],
            'calibration_id':spec['calibration_id'], 'probabilities':out,
            'top1':ranked[0],'top2':ranked[:2],'top3':ranked[:3],
            'half_time_wdl':ht_wdl,'full_time_wdl':ft_wdl,
            'segments':[{'period':PHASES[i],'home_expected_goals':period_h[i],
                         'away_expected_goals':period_a[i],
                         'total_expected_goals':period_h[i]+period_a[i]} for i in range(6)],
            'probability_sum':math.fsum(out.values()),
            'note':'Prematch segment-boundary hazards CONDITIONED on frozen fulltime Q; not minute-by-minute realized events.'}


def _phase(minute):
    if type(minute) is int:
        if not 1<=minute<=90:raise ValueError('minute must be 1..90, use 45+/90+ for stoppage')
        m=minute
    elif isinstance(minute,str) and '+' in minute:
        s=minute.split('+')
        if len(s)!=2 or s[0] not in ('45','90') or not s[1].isdigit() or not 1<=int(s[1])<=30:
            raise ValueError('only 45+N and 90+N valid stoppage minutes')
        m=int(s[0])
    else:raise ValueError('event minute must be integer or 45+N/90+N')
    return 0 if m<=15 else 1 if m<=30 else 2 if m<=45 else 3 if m<=60 else 4 if m<=75 else 5


def _historical(r,cutoff):
    fields={'match_id','observed_at','cutoff','kickoff','result_observed_at','home_xg','away_xg',
            'full_time_score','half_time_score','goal_events'}
    if not isinstance(r,dict) or set(r)!=fields:raise ValueError('complete historical event record required')
    if not isinstance(r['match_id'],str) or not r['match_id'].strip():raise ValueError('match id required')
    if not _time(r['observed_at'])<=_time(r['cutoff'])<_time(r['kickoff'])<_time(r['result_observed_at'])<cutoff:
        raise ValueError('history source/result outside strict prematch fit cutoff')
    for x in (r['home_xg'],r['away_xg']):
        if type(x) not in (int,float) or not math.isfinite(x) or not 0<x<=6:
            raise ValueError('historical xG must be frozen, finite and positive')
    if not isinstance(r['goal_events'],list):raise ValueError('goal events array required')
    counts=[[0,0] for _ in PHASES]
    for e in r['goal_events']:
        if not isinstance(e,dict) or set(e)!={'minute','side'} or e['side'] not in ('home','away'):
            raise ValueError('final credited goal event minute and side required')
        counts[_phase(e['minute'])][0 if e['side']=='home' else 1]+=1
    h,a=_score(r['full_time_score']);hh,ha=_score(r['half_time_score'])
    if (sum(x[0] for x in counts),sum(x[1] for x in counts))!=(h,a) or (
      sum(x[0] for x in counts[:3]),sum(x[1] for x in counts[:3]))!=(hh,ha):
        raise ValueError('goal-event totals must reconcile exactly with HT and FT results')
    return counts


def fit(history, *, asof_cutoff, segment_prior=10., hazard_prior=12.):
    """Research-only shrinkage estimates from completed, permitted prior events.

    The rates approximate score-state exposure at the START of each 15-min period.
    No goal in a match being predicted is available or used.
    """
    asof=_time(asof_cutoff)
    if not isinstance(history,list) or not history:raise ValueError('authorized completed historical records required')
    for prior in (segment_prior,hazard_prior):
        if type(prior) not in (int,float) or not math.isfinite(prior) or prior<=0:
            raise ValueError('priors must be strictly positive and finite')
    seen=set();data=[];latest=None
    for r in history:
        if not isinstance(r,dict) or not isinstance(r.get('match_id'),str):
            raise ValueError('historical record must contain match_id')
        if r['match_id'] in seen:raise ValueError('duplicate historical match')
        seen.add(r['match_id']);c=_historical(r,asof);data.append((r,c))
        latest=max(latest,_time(r['result_observed_at'])) if latest else _time(r['result_observed_at'])
    n_h=[sum(counts[i][0] for _,counts in data) for i in range(6)]
    n_a=[sum(counts[i][1] for _,counts in data) for i in range(6)]
    wh=[(n+float(segment_prior)/6)/(sum(n_h)+float(segment_prior)) for n in n_h]
    wa=[(n+float(segment_prior)/6)/(sum(n_a)+float(segment_prior)) for n in n_a]
    expo={k:0. for k in FACTOR_KEYS};obs={k:0. for k in FACTOR_KEYS}
    for r,counts in data:
        h=a=0
        for i,(gh,ga) in enumerate(counts):
            if h>a:
                expo['home_leading']+=r['home_xg']*wh[i];obs['home_leading']+=gh
                expo['away_trailing']+=r['away_xg']*wa[i];obs['away_trailing']+=ga
            elif a>h:
                expo['home_trailing']+=r['home_xg']*wh[i];obs['home_trailing']+=gh
                expo['away_leading']+=r['away_xg']*wa[i];obs['away_leading']+=ga
            h+=gh;a+=ga
    f={k:max(.7,min(1.3,(obs[k]+hazard_prior)/(expo[k]+hazard_prior))) for k in FACTOR_KEYS}
    return {'research_only':True,'formal_grant':None,'method':'goal-event-time-shares plus lagged-state exposure shrinkage',
            'asof_cutoff':asof_cutoff,'latest_training_result_observed_at':latest.isoformat(),
            'development_n':len(data),'home_shares':wh,'away_shares':wa,'state_factors':f,
            'state_exposure':expo,'state_observed_goals':obs,
            'warnings':['Historical event timestamps and prematch xG must be independently sourced and authorized',
                        'Within-segment score change is approximated only at 15-minute boundaries',
                        'Not validated or automatically granted to Production']}
