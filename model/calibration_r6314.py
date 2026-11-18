"""R6.3.14 research calibration: strictly single-grid, chronological, no grants.

Weights fitted on a development group may only be evaluated on a disjoint
future group. Adjustment changes EVERY cell of research grid coherently; it
must never update M79.3.6 Production or R6.3.13's frozen Q.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime
import math
import joint_bridge_r6312 as joint
import candidate_models_r6313 as candidate
import halftime_bridge_r6313 as halftime
import market_audit_r6313 as market

AXES=('margin','goal')
BINS={'margin':('-3-','-2','-1','0','1','2','3+'),
      'goal':tuple(str(i) for i in range(7))+('7+',)}


def cat(h:int,a:int,axis:str)->str:
    if axis=='goal': return str(h+a) if h+a<7 else '7+'
    if axis=='margin':
        d=h-a
        return '-3-' if d<=-3 else '3+' if d>=3 else str(d)
    raise ValueError('axis must be margin or goal')


def vector(grid:list[dict],axis:str)->dict[str,float]:
    if axis not in AXES:raise ValueError('unknown axis')
    joint.aggregate(grid)  # hardlock checks unique score cells and normalized mass
    p={k:0. for k in BINS[axis]}
    for r in grid:
        h,a=joint.parse_score(r['score'])
        p[cat(h,a,axis)]+=r['probability']
    return p


def _time(s:str)->datetime:
    return candidate._asof(s)


def check_train_test(development:list[dict],test:list[dict])->None:
    """Each record carries match_id, score_matrix, kickoff, cutoff, result_score.

    Chronological study is permitted ONLY if every training fixture finishes
    before any test cutoff. This isn't an immutable vendor-signed timestamp.
    """
    if not development or not test:raise ValueError('need nonempty development and future test')
    ids=set()
    for batch in (development,test):
        for r in batch:
            if set(r)!={'match_id','score_matrix','kickoff','cutoff','result_score'}:
                raise ValueError('record must have exactly five explicit fields')
            if not isinstance(r['match_id'],str) or not r['match_id'] or r['match_id'] in ids:
                raise ValueError('duplicate/invalid fixture id')
            ids.add(r['match_id'])
            if _time(r['cutoff'])>=_time(r['kickoff']):raise ValueError('prediction cutoff must precede kickoff')
            joint.aggregate(r['score_matrix'])
            joint.parse_score(r['result_score'])
    if max(_time(x['kickoff']) for x in development)>=min(_time(x['cutoff']) for x in test):
        raise ValueError('development data overlaps test cutoffs')


def fit_weights(development:list[dict],axis:str,prior_strength:float=30.)->dict:
    """Aggregate category correction with shrinkage; research candidate only."""
    if axis not in AXES:raise ValueError('axis must be goal or margin')
    if isinstance(prior_strength,bool) or not isinstance(prior_strength,(float,int)) or not math.isfinite(prior_strength) or prior_strength<=0:
        raise ValueError('positive finite prior_strength')
    if not development:raise ValueError('no development samples')
    ids=set();obs=Counter();exp=Counter()
    for r in development:
        if r['match_id'] in ids:raise ValueError('duplicate development id')
        ids.add(r['match_id']);p=vector(r['score_matrix'],axis)
        for k,v in p.items():exp[k]+=v
        obs[cat(*joint.parse_score(r['result_score']),axis)]+=1
    n=len(development)
    weights={k:(obs[k]+prior_strength*exp[k]/n)/(exp[k]+prior_strength*exp[k]/n)
             if exp[k]>1e-14 else 1. for k in BINS[axis]}
    return {'axis':axis,'weights':weights,'trained_match_ids':sorted(ids),
            'latest_training_kickoff':max((_time(r['kickoff']) for r in development)).isoformat(),
            'prior_strength':float(prior_strength),'research_only':True,
            'training_count':n,'formal_grant':None}


def apply(grid:list[dict],fit:dict)->list[dict]:
    axis=fit['axis'];weights=fit['weights']
    if set(weights)!=set(BINS[axis]):raise ValueError('all bucket weights required')
    joint.aggregate(grid)
    rows=[]
    for r in grid:
        c=cat(*joint.parse_score(r['score']),axis)
        v=weights[c]
        if not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:raise ValueError('invalid calibration weight')
        rows.append({'score':r['score'],'probability':r['probability']*v})
    z=math.fsum(r['probability'] for r in rows)
    for r in rows:r['probability']/=z
    joint.aggregate(rows)
    return rows


def _stats(p:dict,actual:str,order:tuple[str,...])->dict:
    if set(p)!=set(order) or actual not in order:raise ValueError('probability/outcome label mismatch')
    vals=[float(p[k]) for k in order]
    if any(not math.isfinite(x) or x<0 for x in vals) or abs(math.fsum(vals)-1)>1e-7:
        raise ValueError('probabilities must be normalized')
    idx=order.index(actual);acc=0.;rps=0.
    for i,v in enumerate(vals[:-1]):
        acc+=v;rps+=(acc-(idx<=i))**2
    return {'brier':sum((v-(i==idx))**2 for i,v in enumerate(vals)),
            'log_loss':-math.log(max(1e-15,vals[idx])),
            'ranked_probability_score':rps/(len(order)-1)}


def score_grid(grid:list[dict],score:str,official_signed_line:int|None=None)->dict:
    j=joint.aggregate(grid,official_signed_line)
    h,a=joint.parse_score(score)
    exact=next((r['probability'] for r in grid if r['score']==score),0.)
    d={'score_log_loss':-math.log(max(exact,1e-15)),
       'score_top3_hit':score in j['raw_score_top3'],
       'wdl':_stats(j['wdl_probabilities'],joint.wdl_label(h,a),joint.WDL),
       'goal':_stats(j['goal_bucket_probabilities'],joint.goal_bucket(h,a),joint.GOALS),
       'margin':_stats(vector(grid,'margin'),cat(h,a,'margin'),BINS['margin']),
       'research_only':True}
    if official_signed_line is not None:
        d['JC']=_stats(j['jc_probabilities'],joint.jc_label(h,a,official_signed_line),joint.JC)
        d['JC_letdraw_warning']=letdraw_warning(grid,official_signed_line)
    return d


def letdraw_warning(grid:list[dict],line:int,threshold_pp:float=5.)->dict:
    if type(line) is not int or not (-3<=line<=3):raise ValueError('official signed JC line -3..3 required')
    if not (isinstance(threshold_pp,(float,int)) and 0<threshold_pp<=25):
        raise ValueError('invalid threshold')
    j=joint.aggregate(grid,line)
    p=j['jc_probabilities'];ranking=j['jc_integrated_rank']
    narrow=(p[ranking[0]]-p[ranking[1]])*100<=threshold_pp+1e-9
    return {'risk':'SECOND_REVIEW' if narrow else 'NORMAL_RESEARCH',
            'gap_pp':round((p[ranking[0]]-p[ranking[1]])*100,6),
            'letdraw_probability':p['让平'],
            'most_likely':ranking[0],
            'letdraw_target_margin':-line,
            'two_score_top3_letdraw':sum(x['jc']=='让平' for x in j['score_top3_cross_layer_mapping'])>=2,
            'research_only':True,'auto_reverse':False,'formal_handicap_grant':None}


def evaluate_chronological(development:list[dict],test:list[dict],axis:str,strengths=(5,15,30,60,120,300))->dict:
    check_train_test(development,test)
    def assess(group,fit=None):
        vals=[]
        for r in group:
            g=r['score_matrix'] if fit is None else apply(r['score_matrix'],fit)
            vals.append(score_grid(g,r['result_score'])[axis])
        return {k:math.fsum(x[k] for x in vals)/len(vals) for k in ('log_loss','brier','ranked_probability_score')}
    ranked=[]
    for s in strengths:
        f=fit_weights(development,axis,float(s))
        ranked.append((s,assess(development,f)['log_loss']))
    # Development fit is in-sample; selection is development-only, test remains untouched.
    best=min(ranked,key=lambda x:x[1])[0]
    f=fit_weights(development,axis,best)
    return {'axis':axis,'training_n':len(development),'future_test_n':len(test),
            'selected_prior_strength':best,'dev_selection_scores':ranked,
            'future_baseline':assess(test),'future_candidate':assess(test,f),
            'no_automatic_promotion':True,'production_changed':False}


def compare_same_cutoff(grid:list[dict],odds:dict,cutoff:str)->dict:
    """Actual synchronized paired baseline: quote observed no later than model cutoff.

    Source clock metadata must be supplied externally. An archive's "opening"
    or "closing" label alone does NOT establish identical timestamp.
    """
    if _time(odds['observed_at'])>_time(cutoff):raise ValueError('market quote after model cutoff')
    m=market.devig(odds,joint.aggregate(grid)['wdl_probabilities'])
    return {'status':'SAME_CUTOFF_ELIGIBLE_IF_SOURCE_TIMESTAMP_AUTHENTIC',
            'model_probabilities':joint.aggregate(grid)['wdl_probabilities'],
            'market_mul':m['multiplicative'],'market_power':m['power'],
            'quote_delay_seconds':(_time(cutoff)-_time(odds['observed_at'])).total_seconds(),
            'research_only':True,'official_prediction_unchanged':True}


def fit_halftime_prior(historical:list[dict],test_cutoff:str,smooth:float=100.)->dict:
    """Estimate first-half goal fractions from completed historical fixtures."""
    if not historical:raise ValueError('historical halves needed')
    if smooth<=0 or not math.isfinite(smooth):raise ValueError('invalid smoothing')
    hh=fh=ha=fa=0
    for r in historical:
        if _time(r['kickoff'])>=_time(test_cutoff):raise ValueError('historical match leaks into test')
        h,a=joint.parse_score(r['full_time_score']);ph,pa=joint.parse_score(r['half_time_score'])
        if ph>h or pa>a:raise ValueError('halftime larger than full time')
        fh+=h;fa+=a;hh+=ph;ha+=pa
    return {'fraction_home':(hh+.45*smooth)/(fh+smooth),
            'fraction_away':(ha+.45*smooth)/(fa+smooth),
            'historical_n':len(historical),'research_only':True,'formal_grant':None}


def score_htft(grid:list[dict],full_score:str,half_score:str,spec:dict)->dict:
    a=halftime.aggregate_htft(grid,**spec)
    fh,fa=joint.parse_score(full_score);hh,ha=joint.parse_score(half_score)
    if hh>fh or ha>fa:raise ValueError('invalid half-time score')
    key=joint.wdl_label(hh,ha)+joint.wdl_label(fh,fa)
    out=a['probabilities']
    return {'actual_htft':key,'log_loss':-math.log(max(1e-15,out[key])),
            'brier':sum((v-(k==key))**2 for k,v in out.items()),
            'top3_hit':key in a['top3'],'full_time_marginal':a['full_time_wdl'],
            'research_only':True}
