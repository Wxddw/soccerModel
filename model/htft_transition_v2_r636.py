"""HTFT v2 Shadow: conditional state transition fitted only on earlier matches.

Inputs are one *complete* prematch Q(H,A) and prematch-frozen fractions/tilts.
For every FT score, the conditional distribution over feasible HT scores is
normalized separately, so all fulltime WDL/goal/score marginals are unchanged.
"""
from __future__ import annotations
from datetime import datetime
import math

WDL = ('胜', '平', '负')
PATHS = tuple(h + f for h in WDL for f in WDL)


def _dt(s):
    if not isinstance(s, str):
        raise ValueError('timezone-aware ISO timestamp required')
    try:
        d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('bad ISO timestamp') from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return d


def _score(s):
    if not isinstance(s, str) or ':' not in s:
        raise ValueError('score H:A required')
    parts = s.split(':')
    if len(parts) != 2 or any(not x.isdigit() or str(int(x)) != x for x in parts):
        raise ValueError('canonical nonnegative score H:A required')
    h, a = (int(x) for x in parts)
    if h > 10 or a > 10:
        raise ValueError('score exceeds current finite grid limits')
    return h, a


def _wdl(h, a):
    return '胜' if h > a else '平' if h == a else '负'


def _frac(x):
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 < x < 1:
        raise ValueError('half goal fraction must be finite within (0,1)')
    return float(x)


def _grid(matrix):
    if not isinstance(matrix, list) or not matrix:
        raise ValueError('full prematch Q required')
    rows = []
    seen = set()
    for row in matrix:
        if not isinstance(row, dict) or set(row) != {'score', 'probability'}:
            raise ValueError('grid cell requires only score and probability')
        h, a = _score(row['score'])
        p = row['probability']
        if (h, a) in seen or type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('duplicate or invalid score probability')
        seen.add((h, a)); rows.append((h, a, float(p)))
    if not math.isclose(math.fsum(p for _,_,p in rows), 1., abs_tol=1e-8, rel_tol=0):
        raise ValueError('full prematch Q mass must equal 1; no renormalization')
    return rows


def _conditional(h, a, fh, fa, logits):
    labels = []
    base = []
    for hi in range(h+1):
        hp = math.comb(h,hi)*fh**hi*(1-fh)**(h-hi)
        for ai in range(a+1):
            ap = math.comb(a,ai)*fa**ai*(1-fa)**(a-ai)
            labels.append(_wdl(hi,ai)+_wdl(h,a))
            base.append(hp*ap)
    weighted = [v*math.exp(logits[label]) for v,label in zip(base,labels)]
    norm = math.fsum(weighted)
    if not norm > 0: raise AssertionError('HT conditional normalization failed')
    return labels, [v/norm for v in weighted]


def _logits(raw):
    if raw is None: return {k:0. for k in PATHS}
    if not isinstance(raw, dict) or set(raw) != set(PATHS):
        raise ValueError('must provide all nine transition logits')
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2 for v in raw.values()):
        raise ValueError('transition logits require finite values within [-2,2]')
    return {k:float(raw[k]) for k in PATHS}


def predict(matrix, *, fraction_home, fraction_away, source_id, observed_at,
            cutoff, kickoff, transition_logits=None, latest_training_kickoff=None):
    """Pre-match HTFT nine-class probabilities with exact fulltime marginal lock."""
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError('calibration source_id required')
    if not _dt(observed_at) <= _dt(cutoff) < _dt(kickoff):
        raise ValueError('source, cutoff and kickoff must be in prematch order')
    if transition_logits is not None:
        if latest_training_kickoff is None or not _dt(latest_training_kickoff) < _dt(observed_at):
            raise ValueError('trained logits require strictly earlier training kickoff')
    fh, fa = _frac(fraction_home), _frac(fraction_away)
    logits = _logits(transition_logits)
    rows = _grid(matrix)
    paths = {k:0. for k in PATHS}
    ft = {k:0. for k in WDL}
    ht = {k:0. for k in WDL}
    for h,a,p in rows:
        full_label = _wdl(h,a)
        ft[full_label] += p
        labels, probs = _conditional(h,a,fh,fa,logits)
        for label,q in zip(labels,probs):
            paths[label] += p*q
            ht[label[0]] += p*q
    for k in WDL:
        if abs(math.fsum(paths[h+k] for h in WDL)-ft[k])>1e-9:
            raise AssertionError('fulltime marginal violates frozen score matrix')
    if not math.isclose(math.fsum(paths.values()),1,abs_tol=1e-9):
        raise AssertionError('HTFT mass conservation failed')
    ranked = sorted(PATHS,key=lambda x:(-paths[x], PATHS.index(x)))
    return {'status':'SHADOW_HTFT_V2','research_only':True,'formal_grant':None,
            'method':'conditional_binomial_tilt_by_ft_cell',
            'probabilities':paths, 'top1':ranked[0], 'top2':ranked[:2], 'top3':ranked[:3],
            'full_time_wdl':ft, 'half_time_wdl':ht, 'probability_sum':math.fsum(paths.values()),
            'observed_at':observed_at, 'cutoff':cutoff, 'kickoff':kickoff,
            'latest_training_kickoff':latest_training_kickoff,
            'frozen_fulltime_marginal':True, 'autopromote':False}


def fit_logits(history, *, fraction_home, fraction_away, asof_cutoff,
               ridge=15., iterations=500):
    """Regularized CONDITIONAL HT given exact FT score; development records only.

    Historical fulltime and halftime scores are allowed here, never in predict().
    The estimation is NOT proof of improved external performance.
    """
    fh,fa = _frac(fraction_home), _frac(fraction_away)
    cutoff = _dt(asof_cutoff)
    if not isinstance(history,list) or not history:
        raise ValueError('nonempty completed historical records required')
    if type(ridge) not in (int,float) or not math.isfinite(ridge) or ridge <= 0:
        raise ValueError('positive ridge required')
    if type(iterations) is not int or not 1<=iterations<=3000:
        raise ValueError('bounded iteration count required')
    cases=[]; seen=set(); latest=None
    for r in history:
        if not isinstance(r,dict) or set(r)!={'match_id','kickoff','full_time_score','half_time_score'}:
            raise ValueError('history requires match_id, kickoff, full_time_score, half_time_score')
        kickoff=_dt(r['kickoff'])
        if kickoff >= cutoff: raise ValueError('future or same-cutoff historical fixture blocked')
        mid = r['match_id']
        if not isinstance(mid,str) or not mid or mid in seen:raise ValueError('unique match_id required')
        seen.add(mid);latest = kickoff if latest is None or kickoff>latest else latest
        h,a=_score(r['full_time_score']);hi,ai=_score(r['half_time_score'])
        if hi>h or ai>a:raise ValueError('halftime cannot exceed final score')
        key = _wdl(hi,ai)+_wdl(h,a)
        if key not in PATHS: raise AssertionError('invalid nine-class label')
        cases.append((h,a,key))
    theta = {k:0. for k in PATHS}
    step = .65/(len(cases)+float(ridge))
    for _ in range(iterations):
        grad={k:-float(ridge)*theta[k] for k in PATHS}
        for h,a,actual in cases:
            labels, probs = _conditional(h,a,fh,fa,theta)
            grad[actual]+=1
            for label,prob in zip(labels,probs):grad[label]-=prob
        theta = {k:max(-2.,min(2.,theta[k]+step*grad[k])) for k in PATHS}
    return {'transition_logits':theta, 'fraction_home':fh,'fraction_away':fa,
            'latest_training_kickoff':latest.isoformat(),'development_n':len(cases),
            'research_only':True,'formal_grant':None,'asof_cutoff':asof_cutoff,
            'method':'conditional_multinomial_ridge_fit'}


def evaluate(prediction, *, full_time_score, half_time_score):
    """Score observed HTFT **after** predictions are frozen; do not call in prematch."""
    h,a=_score(full_time_score);hi,ai=_score(half_time_score)
    if hi>h or ai>a:raise ValueError('infeasible halftime')
    key=_wdl(hi,ai)+_wdl(h,a)
    p=prediction['probabilities']
    if set(p)!=set(PATHS):raise ValueError('nine class distribution required')
    return {'actual':key,'log_loss':-math.log(max(1e-15,p[key])),
            'brier':math.fsum((v-(k==key))**2 for k,v in p.items()),
            'top1_hit':prediction['top1']==key,'top2_hit':key in prediction['top2'],
            'top3_hit':key in prediction['top3'],'research_only':True}
