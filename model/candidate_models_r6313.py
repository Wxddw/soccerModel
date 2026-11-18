"""R6.3.13 research-only upstream score-grid alternatives.

Uses externally supplied *prematch* expected-goal parameters; does not fit them
and never accesses results or bookmaker prices. Finite-grid truncation is
measured and bounded before renormalising (never silently dropped).
"""
from __future__ import annotations
from datetime import datetime
import math
import joint_bridge_r6312 as joint

MAX_TEAM_GOALS = 10
MAX_OMITTED_MASS = 0.002  # research safety bound; NOT a fitted parameter
MODELS = ('poisson','dixon_coles','negative_binomial','bivariate_poisson')


def _asof(s: str) -> datetime:
    if not isinstance(s,str): raise ValueError('timestamp string required')
    try: t = datetime.fromisoformat(s.replace('Z','+00:00'))
    except ValueError as e: raise ValueError('timestamp must be ISO8601') from e
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return t


def check_prematch_source(source_id: str, observed_at: str, kickoff: str) -> None:
    if not isinstance(source_id,str) or not source_id.strip():
        raise ValueError('nonblank source_id required')
    if _asof(observed_at) >= _asof(kickoff):
        raise ValueError('source observation must precede kickoff')


def _positive_finite(x, name: str, allow_zero=False) -> float:
    if type(x) not in (int,float) or not math.isfinite(x) or (x < 0 if allow_zero else x <= 0):
        raise ValueError(f'{name} must be finite and positive')
    return float(x)


def _poisson(mu: float) -> list[float]:
    x=[math.exp(-mu)]
    for n in range(1,MAX_TEAM_GOALS+1):x.append(x[-1]*mu/n)
    return x


def _nb(mu: float, size: float) -> list[float]:
    # P(N=n) = Gamma(n+size)/Gamma(size)/n! * (size/(size+mu))**size
    p=[(size/(size+mu))**size]
    for n in range(1,MAX_TEAM_GOALS+1):
        p.append(p[-1]*(n-1+size)/n*(mu/(mu+size)))
    return p


def generate_grid(spec: dict) -> dict:
    """Produce a candidate Q(h,a) for joint.aggregate(), without approval.

    Required: model, home_lambda, away_lambda, source_id, observed_at, kickoff.
    Optional: rho (Dixon-Coles), covariance (bivariate), sizes (negative binomial).
    All variation parameters MUST be prematch inputs rather than fit to results.
    """
    if not isinstance(spec,dict):raise ValueError('model spec must be object')
    allowed={'model','home_lambda','away_lambda','rho','covariance','size_home','size_away',
             'source_id','observed_at','kickoff','spec_id'}
    if set(spec)-allowed: raise ValueError('unexpected parameters in prematch candidate spec')
    name=spec.get('model')
    if name not in MODELS:raise ValueError('unrecognised candidate model')
    check_prematch_source(spec.get('source_id'),spec.get('observed_at'),spec.get('kickoff'))
    h=_positive_finite(spec.get('home_lambda'),'home_lambda',True)
    a=_positive_finite(spec.get('away_lambda'),'away_lambda',True)
    if h>9 or a>9:raise ValueError('xG too high for finite 0..10 grid')
    if name=='dixon_coles':
        rho=spec.get('rho')
        if type(rho) not in (int,float) or not math.isfinite(rho):
            raise ValueError('Dixon-Coles requires an explicit finite rho')
        rho=float(rho)
    else:
        if 'rho' in spec:raise ValueError('rho only for dixon_coles')
        rho=0.
    if name=='negative_binomial':
        if 'size_home' not in spec or 'size_away' not in spec:raise ValueError('two fitted dispersion sizes required')
        size_h=_positive_finite(spec['size_home'],'size_home')
        size_a=_positive_finite(spec['size_away'],'size_away')
        ph,pa=_nb(h,size_h),_nb(a,size_a)
    elif name=='bivariate_poisson':
        cov=_positive_finite(spec.get('covariance'),'covariance',True)
        if cov>min(h,a):raise ValueError('covariance exceeds smaller lambda')
        ph,pa,pcommon=_poisson(h-cov),_poisson(a-cov),_poisson(cov)
    else:ph,pa=_poisson(h),_poisson(a)
    if name not in ('negative_binomial','bivariate_poisson') and any(k in spec for k in ('size_home','size_away','covariance')):
        raise ValueError('dispersion/covariance incompatible with specified model')
    if name=='negative_binomial' and 'covariance' in spec:raise ValueError('covariance incompatible with negative binomial')
    if name=='bivariate_poisson' and any(k in spec for k in ('size_home','size_away')):
        raise ValueError('dispersion incompatible with bivariate model')
    rows=[]
    for i in range(MAX_TEAM_GOALS+1):
        for j in range(MAX_TEAM_GOALS+1):
            if name=='bivariate_poisson':
                p=math.fsum(ph[i-k]*pa[j-k]*pcommon[k] for k in range(min(i,j)+1))
            else:
                p=ph[i]*pa[j]
                if name=='dixon_coles':
                    tau={(0,0):1-h*a*rho,(0,1):1+h*rho,
                         (1,0):1+a*rho,(1,1):1-rho}.get((i,j),1.)
                    if tau<0:raise ValueError('Dixon-Coles rho yields negative low-score mass')
                    p*=tau
            if p<0 or not math.isfinite(p):raise ValueError('invalid probability')
            rows.append({'score':f'{i}:{j}','probability':p})
    mass=math.fsum(r['probability'] for r in rows)
    missing=1-mass
    if missing < -1e-10:
        raise ValueError('generated probability mass exceeds one')
    if missing>MAX_OMITTED_MASS:
        raise ValueError(f'0..10 score grid drops {missing:.5g} mass; no automatic acceptance')
    for r in rows:r['probability']/=mass
    check=joint.aggregate(rows)
    return {'status':'RESEARCH_CANDIDATE_GRID_VALIDATED',
            'model':name,'source_id':spec['source_id'],'observed_at':spec['observed_at'],
            'kickoff':spec['kickoff'],'grid':rows,
            'parameters':{k:v for k,v in spec.items() if k in ('home_lambda','away_lambda','rho','covariance','size_home','size_away')},
            'omitted_tail_mass_before_normalization':max(0.,missing),
            'finite_grid_bound':MAX_TEAM_GOALS,'probability_sum':check['joint_mass'],
            'research_only':True,'fitted_on_user_data':False,'official_model_changed':False}
