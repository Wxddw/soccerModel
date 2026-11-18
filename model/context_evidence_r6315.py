"""Research-only, fail-closed, pre-match context evidence audit for M79 Shadow.

No prediction adjustments are produced or authorised by this module. Actual
post-kickoff events, in-play coaching, realised goalkeeper saves and random
outcomes never enter pre-match features. Evidence families are deduplicated.
"""
from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import math

FACTORS = {
    'squad_quality_depth', 'injury_suspension', 'tactical_matchup',
    'coach_preparation', 'recent_form_confidence', 'workload_rest',
    'motivation_pressure', 'referee_prematch_profile',
    'goalkeeper_set_piece_prematch', 'home_crowd', 'weather_pitch',
}
IN_PLAY_ONLY = {'actual_key_events_refereeing', 'actual_coach_adjustments',
                'realized_goalkeeper_performance', 'realized_randomness'}
REQUIRED={'factor','value','evidence_asof','source_url','source_family','confidence','availability'}


def _time(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('time must be an ISO-8601 timezone-aware string')
    try: parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise ValueError('bad timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('timezone is required')
    return parsed.astimezone(timezone.utc)


def audit(packet:dict)->dict:
    """Validate a research evidence packet, without granting changes to Production.

    factor/value: numeric contextual severity from -1 to +1, purely a feature
    placeholder; it MUST NOT be treated as a calibrated likelihood/weight.
    """
    if not isinstance(packet,dict) or set(packet)!={'cutoff','kickoff','observations'}:
        raise ValueError('cutoff, kickoff, observations required; no actual result fields')
    cutoff=_time(packet['cutoff']);kickoff=_time(packet['kickoff'])
    if cutoff>=kickoff:raise ValueError('cutoff must precede kickoff')
    if not isinstance(packet['observations'],list):raise ValueError('observations must be list')
    accepted=[];blocked=[];families=set();seen=set()
    for i,obs in enumerate(packet['observations']):
        if not isinstance(obs,dict) or set(obs)!=REQUIRED:
            raise ValueError('every observation requires exact pre-match evidence fields')
        factor=obs['factor']
        if not isinstance(factor,str):raise ValueError('factor must be string')
        if factor in IN_PLAY_ONLY:
            blocked.append({'index':i,'factor':factor,'reason':'IN_PLAY_OR_POSTMATCH_FORBIDDEN'})
            continue
        if factor not in FACTORS:raise ValueError('unknown factor')
        asof=_time(obs['evidence_asof'])
        if asof>cutoff or asof>=kickoff:
            blocked.append({'index':i,'factor':factor,'reason':'FUTURE_OR_POST_CUTOFF'})
            continue
        url=obs['source_url'];family=obs['source_family']
        if not isinstance(url,str) or urlparse(url).scheme!='https' or not urlparse(url).netloc:
            blocked.append({'index':i,'factor':factor,'reason':'MISSING_AUTHORITATIVE_SOURCE'})
            continue
        if not isinstance(family,str) or not family.strip():
            raise ValueError('source family required for deduplication')
        if obs['availability'] not in ('confirmed','expected','unavailable'):
            raise ValueError('bad evidence availability')
        if obs['availability']=='unavailable':
            blocked.append({'index':i,'factor':factor,'reason':'NOT_AVAILABLE_PREMATCH'})
            continue
        c=obs['confidence'];val=obs['value']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (c,val)):
            raise ValueError('confidence/value must be finite numeric')
        if not 0<=c<=1 or not -1<=val<=1:
            raise ValueError('confidence or feature out of range')
        key=(factor,family.strip().lower())
        if key in seen:
            blocked.append({'index':i,'factor':factor,'reason':'DUPLICATE_EVIDENCE_FAMILY'})
            continue
        seen.add(key);families.add(family.strip().lower())
        accepted.append({'index':i,'factor':factor,'availability':obs['availability'],
                         'evidence_family':family.strip(),'asof':asof.isoformat(),
                         'confirmed':obs['availability']=='confirmed'})
    eligible_factors=sorted({x['factor'] for x in accepted})
    return {'status':'RESEARCH_EVIDENCE_ONLY','eligible_factors':eligible_factors,
            'accepted':accepted,'blocked':blocked,'distinct_evidence_families':len(families),
            'automatic_model_weights':None,'change_production':False,
            'allow_outcome_reversal':False,'allow_core_grant':False,
            'forward_validation_certified':False,
            'coverage':{'eligible':len(eligible_factors),'total_prematch_dimensions':len(FACTORS)}}
