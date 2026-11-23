"""R6.3.6: conditional joint-score calibration challenger, research ONLY.

Feature tilts conditional on fixed final WDL. The original frozen score Q is
NEVER modified; new Q changes Goal/Handicap/Score/HTFT candidate outputs and
requires independent paired validation before any Production use.

Fit exclusively on complete, previously OBSERVED historical fulltime results
and frozen prematch Q. Insufficient/no prior training => fail closed.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
import math

FEATURES = ('four_plus', 'five_plus', 'three_goal_margin', 'both_2plus', 'low_01', 'exact_3')
REGIMES = ('LOW', 'CENTRAL', 'HIGH')
WDL = ('胜', '平', '负')
MIN_TRAIN = 80
MIN_REGIME = 35
MAX_ABS_THETA = .65  # exploratory safety bound, not learned or promoted


def timestamp(s):
    if not isinstance(s, str):
        raise ValueError('aware ISO time required')
    try:
        d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError as e:
        raise ValueError('bad timestamp') from e
    if d.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return d


def score(s):
    if not isinstance(s, str) or ':' not in s:
        raise ValueError('score H:A required')
    p = s.split(':')
    if len(p) != 2 or any(not x.isdecimal() or str(int(x)) != x for x in p):
        raise ValueError('nonnegative canonical score required')
    h, a = (int(x) for x in p)
    if h > 30 or a > 30:
        raise ValueError('score outside 0..30 model capacity')
    return h, a


def _wdl(h, a):
    return '胜' if h > a else '平' if h == a else '负'


def grid(raw):
    """Accept full N by N array, or exhaustive nonzero {(score,prob)} rows.

    Sparse score entries are allowed if they carry EXACT 1 total mass. Never
    renormalize a missing tail or a wrong mass to 1.
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError('complete nonempty score grid required')
    g = {}
    if all(isinstance(x, dict) for x in raw):
        for row in raw:
            if set(row) != {'score', 'probability'}:
                raise ValueError('only exact score and probability fields accepted')
            k = score(row['score'])
            if k in g:
                raise ValueError('duplicate score cell')
            g[k] = row['probability']
    else:
        n = len(raw)
        if not 1 <= n <= 31 or any(not isinstance(row, list) or len(row) != n for row in raw):
            raise ValueError('square complete 1..31 score matrix required')
        g = {(h, a): raw[h][a] for h in range(n) for a in range(n)}
    for p in g.values():
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('finite valid probability required')
    if abs(math.fsum(g.values()) - 1.) > 1e-8:
        raise ValueError('incomplete original score probability mass')
    return {k: float(v) for k, v in g.items()}


def features(h, a):
    total = h + a
    return (float(total >= 4), float(total >= 5), float(abs(h-a) >= 3),
            float(h >= 2 and a >= 2), float(total <= 1), float(total == 3))


def regime(g):
    expectation = math.fsum((h+a)*p for (h,a), p in g.items())
    return 'LOW' if expectation < 2.6 else 'HIGH' if expectation >= 3.7 else 'CENTRAL'


def tilt_within_wdl(g, weights):
    """Reweight score cells inside EACH WDL class; WDL remains precisely frozen."""
    if not isinstance(weights, list) or len(weights) != len(FEATURES):
        raise ValueError('six fitted feature weights needed')
    if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > MAX_ABS_THETA for v in weights):
        raise ValueError('weight outside permissible fitted research guard')
    mass = {w: 0. for w in WDL}
    scaled = {}
    normalizer = {w: 0. for w in WDL}
    for (h,a), p in g.items():
        w = _wdl(h,a)
        mass[w] += p
        x = features(h,a)
        newp = p * math.exp(math.fsum(weights[i] * x[i] for i in range(len(weights))))
        scaled[h,a] = newp
        normalizer[w] += newp
    output = {}
    for (h,a), p in scaled.items():
        w = _wdl(h,a)
        if mass[w] and not normalizer[w]:
            raise ArithmeticError('conditional class has no numerical probability')
        output[h,a] = p * mass[w] / normalizer[w] if mass[w] else 0.
    for w in WDL:
        actual = math.fsum(p for (h,a),p in output.items() if _wdl(h,a) == w)
        if abs(actual - mass[w]) > 1e-10:
            raise ArithmeticError('fixed WDL marginal moved')
    if abs(math.fsum(output.values()) - 1.) > 1e-9:
        raise ArithmeticError('total mass moved')
    return output


def aggregates(g, official_line=None):
    if official_line is not None and (type(official_line) is not int or not -3 <= official_line <= 3):
        raise ValueError('only official signed integer JC line in -3..3 supported')
    result = {'wdl': {w: 0. for w in WDL},
              'goals': {str(i):0. for i in range(7)} | {'7+':0.},
              'score_top3': [], 'jc':None,
              'goal_top3':[], 'goal_dual':[], 'moment_expected_goals':0.}
    if official_line is not None:
        result['jc'] = {'让胜':0.,'让平':0.,'让负':0.}
    for (h,a),p in g.items():
        result['wdl'][_wdl(h,a)] += p
        result['goals'][str(h+a) if h+a <= 6 else '7+'] += p
        result['moment_expected_goals'] += (h+a)*p
        if official_line is not None:
            d = h + official_line - a
            result['jc']['让胜' if d>0 else '让平' if d==0 else '让负'] += p
    s = sorted(g, key=lambda k:(-g[k],k))
    result['score_top3']=[f'{h}:{a}' for h,a in s[:3]]
    ranks=sorted(result['goals'],key=lambda k:(-result['goals'][k],int(k.rstrip('+'))))
    result['goal_top3'] = ranks[:3]
    # "7+" is a bucket, NOT an exact integer! Do not mislabel as integer Goal Top3.
    exact=[k for k in ranks if k != '7+']
    result['goal_dual'] = exact[:2]
    return result


def _ready_history(r, asof):
    keys = {'match_id','source_id','observed_at','cutoff','kickoff',
            'result_observed_at','score_matrix','actual_score','authorized_for_analysis'}
    if not isinstance(r,dict) or set(r) != keys or r['authorized_for_analysis'] is not True:
        raise ValueError('licensed complete historical training record required')
    if not all(isinstance(r[k],str) and r[k].strip() for k in ('match_id','source_id')):
        raise ValueError('source and match ids required')
    if not timestamp(r['observed_at']) <= timestamp(r['cutoff']) < timestamp(r['kickoff']) < timestamp(r['result_observed_at']) < asof:
        raise ValueError('results must be known strictly before training as-of')
    g=grid(r['score_matrix']);actual=score(r['actual_score'])
    if g.get(actual,0.)<=0:
        raise ValueError('observed final score has zero support under frozen historical Q')
    return g,actual


def _grad_one(g, actual, weights):
    category=_wdl(*actual)
    entries=[];denom=0.;expfeat=[0.]*len(FEATURES)
    for (h,a),p in g.items():
        if not p or _wdl(h,a)!=category:continue
        x=features(h,a)
        val=p*math.exp(math.fsum(w*z for w,z in zip(weights,x)))
        entries.append((val,x));denom+=val
    if denom<=0:
        raise ArithmeticError('zero conditional support')
    for v,x in entries:
        for i,z in enumerate(x): expfeat[i]+=v*z/denom
    truth=features(*actual)
    return [truth[i]-expfeat[i] for i in range(len(FEATURES))]


def _fit_one(pairs, *, ridge, step, iterations):
    w=[0.]*len(FEATURES)
    for it in range(iterations):
        grad=[-ridge*x for x in w]
        for g,actual in pairs:
            dg=_grad_one(g,actual,w)
            for j,v in enumerate(dg):grad[j]+=v/len(pairs)
        # decaying step prevents late oscillations on small training segments
        lr=step/(1.+it/100.)
        w=[max(-MAX_ABS_THETA,min(MAX_ABS_THETA,w[j]+lr*grad[j])) for j in range(len(w))]
    return w


def fit(history, *, asof_cutoff, calibration_id, ridge=.3, step=.25, iterations=160):
    """Fit only when >=80 verified earlier matches; per-regime >=35.

    Minimums and clips are provisional research safety gates, not performance
    tuned values. Results known on Nov22 cannot be used to train the model for
    the Nov22 fixtures; later historical development cannot be a clean holdout.
    """
    asof=timestamp(asof_cutoff)
    if not isinstance(history,list) or len(history)<MIN_TRAIN:
        raise ValueError('insufficient prior authorized historical records; minimum 80')
    if not isinstance(calibration_id,str) or not calibration_id.strip():
        raise ValueError('nonempty calibration ID required')
    if type(ridge) not in (float,int) or not .05 <= ridge <= 1.5 or type(step) not in (int,float) or not 0 < step <= .5:
        raise ValueError('regularizer/step outside research bounds')
    if type(iterations) is not int or not 20 <= iterations <= 500:
        raise ValueError('iterations out of bounds')
    by={k:[] for k in REGIMES}
    latest=None;ids=set();digest=sha256()
    for r in history:
        if not isinstance(r,dict) or r.get('match_id') in ids:
            raise ValueError('duplicate or bad training match')
        ids.add(r['match_id'])
        g,actual=_ready_history(r,asof)
        by[regime(g)].append((g,actual))
        when=timestamp(r['result_observed_at'])
        if latest is None or when>latest:latest=when
        digest.update(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    params={}
    for label,pairs in by.items():
        if len(pairs)>=MIN_REGIME:
            params[label]=_fit_one(pairs,ridge=ridge,step=step,iterations=iterations)
    if not params:
        raise ValueError('no regime with at least 35 eligible earlier results')
    return {'version':'R636_JOINT_TAIL_V0.1_SHADOW','research_only':True,'formal_grant':None,
            'asof_cutoff':asof_cutoff,'latest_result_observed_at':latest.isoformat(),
            'training_size':len(history),'counts_by_regime':{k:len(v) for k,v in by.items()},
            'weights_by_regime':params,'calibration_id':calibration_id,
            'training_hash':digest.hexdigest(),'trained_match_ids':sorted(ids),
            'ridge':ridge,'safety_bound':MAX_ABS_THETA,
            'note':'Fitted exclusively on prior complete games; not production certified'}


def predict(packet, fitted):
    keys={'match_id','source_id','observed_at','cutoff','kickoff','score_matrix','official_jc_line'}
    if not isinstance(packet,dict) or set(packet)!=keys:
        raise ValueError('prematch input only; postmatch data or undeclared fields blocked')
    if not isinstance(packet['match_id'],str) or not packet['match_id'].strip() or not isinstance(packet['source_id'],str) or not packet['source_id'].strip():
        raise ValueError('prematch source and match id required')
    if not isinstance(fitted,dict) or fitted.get('research_only') is not True or fitted.get('formal_grant') is not None:
        raise ValueError('non-production trained shadow calibration required')
    if not timestamp(fitted['latest_result_observed_at']) < timestamp(fitted['asof_cutoff']) <= timestamp(packet['observed_at']) <= timestamp(packet['cutoff']) < timestamp(packet['kickoff']):
        raise ValueError('training results not available before prematch Q cutoff')
    if packet['match_id'] in fitted['trained_match_ids']:
        raise ValueError('current game appeared in training data')
    g=grid(packet['score_matrix']);name=regime(g)
    if name not in fitted['weights_by_regime']:
        raise ValueError('no previously fitted regime; fail closed without changing Q')
    weights=fitted['weights_by_regime'][name]
    candidate=tilt_within_wdl(g,weights)
    prior=aggregates(g,packet['official_jc_line'])
    updated=aggregates(candidate,packet['official_jc_line'])
    for k in WDL:
        if abs(prior['wdl'][k]-updated['wdl'][k])>1e-10:raise ArithmeticError('WDL hardlock failed')
    # Output complete candidate, never edit original packet or claim official picks.
    frozen_hash=sha256(json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'version':'R636_JOINT_TAIL_V0.1_SHADOW','research_only':True,
            'formal_grant':None,'production_changed':False,
            'source_id':packet['source_id'],'match_id':packet['match_id'],'source_sha256':frozen_hash,
            'calibration_id':fitted['calibration_id'],'training_hash':fitted['training_hash'],
            'training_n':fitted['training_size'],'regime':name,'fitted_weights':weights,
            'original':prior,'candidate':updated,
            'candidate_score_grid':[{'score':f'{h}:{a}','probability':p} for (h,a),p in sorted(candidate.items())],
            'risk_note':'Joint Score/Goal/JC/HTFT candidate ONLY; WDL unchanged; do not update released picks.'}
