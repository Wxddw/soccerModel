"""Six-phase PREMATCH HTFT path research with separate one/two-goal lead regimes.

No in-play events are allowed at prediction. The dynamic path process is
CONDITIONED on each unchanged fulltime joint-score Q(H,A) cell.

The Nov22 Barcelona 0-2->3-2 / Marseille 2-0->2-3 results are diagnostic
examples only and are NOT used to fit any coefficient in this package.
"""
from __future__ import annotations
from collections import defaultdict
import math
from joint_tail_calibration_shadow_r636 import grid, timestamp, score, _wdl, WDL

PHASES=('00-15','16-30','31-45+','46-60','61-75','76-90+')
PATHS=tuple(a+b for a in WDL for b in WDL)
STATES=('LEAD_2PLUS','LEAD_1','LEVEL','TRAIL_1','TRAIL_2PLUS')
FACTORS=tuple(f'{side}_{state}' for side in ('home','away') for state in
              ('leading_1','leading_2plus','trailing_1','trailing_2plus'))
MIN_HISTORY=80


def _bucket(diff):
    return 'LEAD_2PLUS' if diff>=2 else 'LEAD_1' if diff==1 else 'TRAIL_2PLUS' if diff<=-2 else 'TRAIL_1' if diff==-1 else 'LEVEL'


def _shares(v):
    if (not isinstance(v,list) or len(v)!=6 or
        any(type(z) not in (int,float) or not math.isfinite(z) or z<=0 for z in v) or
        abs(math.fsum(v)-1)>1e-8):
        raise ValueError('strict six-segment probability shares required')
    return [float(x) for x in v]


def _factors(r):
    if not isinstance(r,dict) or set(r)!=set(FACTORS) or any(
        type(r[k]) not in (int,float) or not math.isfinite(r[k]) or not .5<=r[k]<=1.8 for k in FACTORS):
        raise ValueError('eight explicit bounded prefit lead/trail factors required')
    return {k:float(r[k]) for k in FACTORS}


def _intensity_multipliers(diff,f):
    if diff==0:return 1.,1.
    if diff>0:
        k='1' if diff==1 else '2plus'
        return f['home_leading_'+k],f['away_trailing_'+k]
    k='1' if diff==-1 else '2plus'
    return f['home_trailing_'+k],f['away_leading_'+k]


def _poisson(lam,limit):
    seq=[math.exp(-lam)]
    for j in range(1,limit+1):seq.append(seq[-1]*lam/j)
    return seq


def _phase(m):
    if type(m) is int and 1 <= m <= 90:
        base=m
    elif isinstance(m,str) and '+' in m:
        a=m.split('+')
        if len(a)!=2 or a[0] not in ('45','90') or not a[1].isdigit() or not 1<=int(a[1])<=30:
            raise ValueError('only 45+N and 90+N injury time supported')
        base=int(a[0])
    else:raise ValueError('goal event minute must be 1..90 or 45+N/90+N')
    return 0 if base<=15 else 1 if base<=30 else 2 if base<=45 else 3 if base<=60 else 4 if base<=75 else 5


def predict(packet,calibration):
    keys={'match_id','source_id','observed_at','cutoff','kickoff','score_matrix','home_xg','away_xg'}
    if not isinstance(packet,dict) or set(packet)!=keys:
        raise ValueError('prematch exact fields required; no actual HT or goals')
    if not isinstance(packet['match_id'],str) or not packet['match_id'] or not isinstance(packet['source_id'],str) or not packet['source_id']:
        raise ValueError('match and source ids required')
    if not isinstance(calibration,dict) or set(calibration)!={
        'calibration_id','latest_result_observed_at','asof_cutoff','training_n','training_match_ids','home_shares','away_shares','state_factors','research_only','formal_grant'}:
        raise ValueError('complete previous historical calibration object required')
    if calibration['research_only'] is not True or calibration['formal_grant'] is not None or (
        type(calibration['training_n']) is not int or calibration['training_n']<MIN_HISTORY):
        raise ValueError('not an eligible prior historical Shadow calibration')
    if packet['match_id'] in calibration['training_match_ids']:
        raise ValueError('same match in training prohibited')
    if not timestamp(calibration['latest_result_observed_at']) < timestamp(calibration['asof_cutoff']) <= timestamp(packet['observed_at']) <= timestamp(packet['cutoff']) < timestamp(packet['kickoff']):
        raise ValueError('trained coefficients or source observation not available before cutoff')
    for k in ('home_xg','away_xg'):
        v=packet[k]
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=6:
            raise ValueError('finite prematch team xG (0,6] required')
    wh=_shares(calibration['home_shares']);wa=_shares(calibration['away_shares'])
    f=_factors(calibration['state_factors'])
    q=grid(packet['score_matrix'])
    hmax=max(h for (h,a),p in q.items() if p>0)
    amax=max(a for (h,a),p in q.items() if p>0)
    if hmax>13 or amax>13:
        raise ValueError('time-segment DP only supports full score 0..13; never discard 14+ tails')
    states={(0,0,None):[1.]+[0.]*12}
    for phase in range(6):
        nxt=defaultdict(lambda:[0.]*13)
        for (h,a,half),carry in states.items():
            hm,am=_intensity_multipliers(h-a,f)
            hp=_poisson(packet['home_xg']*wh[phase]*hm,hmax-h)
            ap=_poisson(packet['away_xg']*wa[phase]*am,amax-a)
            for dh,ph in enumerate(hp):
                if ph<=0:continue
                for da,pa in enumerate(ap):
                    pp=ph*pa
                    if pp<=0:continue
                    hh,aa=h+dh,a+da
                    label=_bucket(hh-aa) if phase==2 else half
                    row=nxt[hh,aa,label]
                    m=pp*carry[0]
                    row[0]+=m
                    for idx in range(phase):
                        row[1+idx]+=pp*carry[1+idx]
                        row[7+idx]+=pp*carry[7+idx]
                    row[1+phase]+=m*dh
                    row[7+phase]+=m*da
        states=nxt
    terminal=defaultdict(float)
    for (h,a,ht),v in states.items():terminal[h,a]+=v[0]
    paths={k:0. for k in PATHS}
    half_buckets={k:0. for k in STATES}
    moments_h=[0.]*6;moments_a=[0.]*6
    two_goal_lead_lost=0.;two_goal_comeback=0.
    for (h,a,ht),v in states.items():
        qmass=q.get((h,a),0.)
        if not qmass:continue
        if terminal[h,a]<=1e-280:raise ValueError('frozen Q cell has no usable conditional timeline support')
        scale=qmass/terminal[h,a];mass=v[0]*scale
        ft=_wdl(h,a)
        halftime='胜' if ht in ('LEAD_2PLUS','LEAD_1') else '负' if ht in ('TRAIL_2PLUS','TRAIL_1') else '平'
        paths[halftime+ft]+=mass
        half_buckets[ht]+=mass
        if ht=='LEAD_2PLUS' and ft!='胜' or ht=='TRAIL_2PLUS' and ft!='负':
            two_goal_lead_lost+=mass
        if ht=='LEAD_2PLUS' and ft=='负' or ht=='TRAIL_2PLUS' and ft=='胜':
            two_goal_comeback+=mass
        for j in range(6):
            moments_h[j]+=v[1+j]*scale
            moments_a[j]+=v[7+j]*scale
    if abs(math.fsum(paths.values())-1)>1e-8:raise AssertionError('HTFT mass conservation failed')
    for ft in WDL:
        left=math.fsum(p for (h,a),p in q.items() if _wdl(h,a)==ft)
        right=math.fsum(paths[ht+ft] for ht in WDL)
        if abs(left-right)>1e-8:raise AssertionError('frozen fulltime WDL changed')
    if abs(math.fsum(moments_h)-math.fsum(h*p for (h,a),p in q.items()))>1e-8:
        raise AssertionError('time-segment home goal expectation changed')
    if abs(math.fsum(moments_a)-math.fsum(a*p for (h,a),p in q.items()))>1e-8:
        raise AssertionError('time-segment away goal expectation changed')
    ranked=sorted(PATHS,key=lambda s:(-paths[s],PATHS.index(s)))
    return {'version':'HTFT_MARGIN2_TIMESEG_SHADOW_V0.1','research_only':True,
            'formal_grant':None,'production_changed':False,
            'calibration_id':calibration['calibration_id'],'match_id':packet['match_id'],
            'probabilities':paths,'top1':ranked[0],'top2':ranked[:2],'top3':ranked[:3],
            'half_time_margin_bucket_probability':half_buckets,
            'probability_two_goal_lead_not_won':two_goal_lead_lost,
            'probability_two_goal_comeback_win':two_goal_comeback,
            'segments':[{'minute_range':PHASES[i],'home_goal_expectation':moments_h[i],
                         'away_goal_expectation':moments_a[i]} for i in range(6)],
            'note':'Eight pregame-learned state factors only; no actual in-play events or 2-goal result hindsight.'}


def fit(history, *, asof_cutoff, calibration_id, prior=15.):
    """Fit 8 state buckets from previously completed, licensed goal-minute events."""
    if not isinstance(history,list) or len(history)<MIN_HISTORY:
        raise ValueError('at least 80 earlier authorized goal-minute match records required')
    if not isinstance(calibration_id,str) or not calibration_id or type(prior) not in (float,int) or not 1<=prior<=100:
        raise ValueError('invalid research calibration ID / positive shrinkage prior')
    end=timestamp(asof_cutoff)
    required={'match_id','source_id','observed_at','cutoff','kickoff','result_observed_at',
              'home_xg','away_xg','full_time_score','half_time_score','goal_events','authorized_for_analysis'}
    ids=set();dev=[];hcounts=[0.]*6;acounts=[0.]*6;latest=None
    for r in history:
        if not isinstance(r,dict) or set(r)!=required or r['authorized_for_analysis'] is not True:
            raise ValueError('complete licensed historical match with goal events required')
        if r['match_id'] in ids:raise ValueError('duplicate historical match')
        ids.add(r['match_id'])
        if not timestamp(r['observed_at'])<=timestamp(r['cutoff'])<timestamp(r['kickoff'])<timestamp(r['result_observed_at'])<end:
            raise ValueError('historical result or prematch observation temporally invalid')
        for label in ('home_xg','away_xg'):
            v=r[label]
            if type(v) not in (float,int) or not math.isfinite(v) or not 0<v<=6:
                raise ValueError('prematch expected goals positive finite and licensed')
        if not isinstance(r['goal_events'],list):raise ValueError('historical goal events required')
        counts=[[0,0] for _ in range(6)]
        for event in r['goal_events']:
            if not isinstance(event,dict) or set(event)!={'minute','side'} or event['side'] not in ('home','away'):
                raise ValueError('credited goal event only; no future lineups/cards')
            counts[_phase(event['minute'])][0 if event['side']=='home' else 1]+=1
        full=score(r['full_time_score']);half=score(r['half_time_score'])
        if (sum(x[0] for x in counts),sum(x[1] for x in counts))!=full or (
            sum(x[0] for x in counts[:3]),sum(x[1] for x in counts[:3]))!=half:
            raise ValueError('credited goal minutes do not reconcile to HT/FT')
        for j in range(6):hcounts[j]+=counts[j][0];acounts[j]+=counts[j][1]
        dev.append((r,counts));observed=timestamp(r['result_observed_at'])
        latest=max(latest,observed) if latest else observed
    wh=[(x+prior/6)/(sum(hcounts)+prior) for x in hcounts]
    wa=[(x+prior/6)/(sum(acounts)+prior) for x in acounts]
    expo={k:0. for k in FACTORS};observed_goals={k:0. for k in FACTORS}
    for r,counts in dev:
        h=a=0
        for j,(dh,da) in enumerate(counts):
            diff=h-a
            if diff!=0:
                pos='1' if abs(diff)==1 else '2plus'
                hlabel='home_'+('leading_' if diff>0 else 'trailing_')+pos
                alabel='away_'+('leading_' if diff<0 else 'trailing_')+pos
                expo[hlabel]+=r['home_xg']*wh[j];expo[alabel]+=r['away_xg']*wa[j]
                observed_goals[hlabel]+=dh;observed_goals[alabel]+=da
            h+=dh;a+=da
    factors={k:max(.7,min(1.3,(observed_goals[k]+prior)/(expo[k]+prior))) for k in FACTORS}
    return {'calibration_id':calibration_id,'asof_cutoff':asof_cutoff,
            'latest_result_observed_at':latest.isoformat(),'training_n':len(history),
            'training_match_ids':sorted(ids),'home_shares':wh,'away_shares':wa,
            'state_factors':factors,'research_only':True,'formal_grant':None}
