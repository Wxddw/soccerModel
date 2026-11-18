"""Shadow R6.3.4: Motivation (MSI) and Effective Squad Rating (ESR).

Research audit only: no fitted weights, no odds adjustments, no decision grants.
Strict pre-match inputs and source timestamps. Requires both teams to estimate
relative effective strength. Motivation does not mean the motivated team wins.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import math
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.4_20261104"
ROLES = {"goalkeeper", "center_back", "fullback", "defensive_midfielder", "central_midfielder", "attacking_midfielder", "winger", "striker", "other"}
STAKES = {"title", "qualification", "promotion", "relegation", "knockout", "group_survival", "playoff", "routine", "unknown"}
URGENCY = {"high", "medium", "low", "unknown"}
CONTEXT = {"league", "group", "knockout", "cup", "friendly"}
BASIS = {"official_table_and_rules", "official_knockout_regulations", "official_schedule", "official_team_statement", "journalist_projection"}
REQUIRED_MINUTES = 990.0  # Each side has 11 players on field for 90 minutes; projected subs may share time.
# A research alarm, not a calibrated winning-probability coefficient.
DELTA_REVIEW_THRESHOLD = 2.0  # rating units on a [0,100] scale, per on-field player


def _dated_record(record: Any, cutoff: datetime, label: str, *, allowed_basis: set[str] | None = None) -> tuple[str, datetime]:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be a source object")
    sid = record.get('source_id')
    if not isinstance(sid, str) or not sid.strip():
        raise ValueError(f"{label}.source_id is required")
    dt = base._time(record.get('observed_at'), f'{label}.observed_at')
    if dt > cutoff:
        raise ValueError(f'{label} is post-cutoff; do not leak future info')
    if allowed_basis is not None and record.get('basis') not in allowed_basis:
        raise ValueError(f'{label}.basis unsupported')
    return sid, dt


def _check_cutoff(packet: dict) -> datetime:
    cutoff = base._time(packet.get('cutoff'), 'cutoff')
    kickoff = base._time(packet.get('kickoff'), 'kickoff')
    if cutoff >= kickoff:
        raise ValueError('cutoff must be before kickoff')
    return cutoff


def effective_squad_strength(squads: Any, cutoff: datetime) -> dict:
    """Minute-adjusted delta vs normal baseline, NOT an outcome probability.

    Both complete teams need 990 person-minutes for baseline and projection.
    Independent player ratings must be fitted before the snapshot (not to the match result).
    For projected lineups we expose uncertainty and never treat them as confirmed XI.
    """
    if squads is None:
        return {'status':'UNKNOWN_NO_PREMATCH_SQUAD_MATRIX', 'sides':{}, 'relative_shift':None,
                'direction_signal':'UNKNOWN', 'numeric_probability_change':False}
    if not isinstance(squads, dict) or set(squads) != {'home','away'}:
        raise ValueError('squads must contain exactly home and away')
    results = {}
    for side in ('home','away'):
        data = squads[side]
        if not isinstance(data,dict): raise ValueError(f'{side} squad must be object')
        status = data.get('lineup_status')
        if status not in ('confirmed', 'projected'):
            raise ValueError('lineup_status must be confirmed or projected')
        minutes_source, _ = _dated_record(data.get('minutes_source'), cutoff, f'{side}.minutes_source')
        model_source,_ = _dated_record(data.get('rating_model_source'),cutoff,f'{side}.rating_model_source')
        mm=data['minutes_source'].get('method')
        if status=='confirmed' and mm!='confirmed_starters_projected_minutes':
            raise ValueError('confirmed lineup status requires confirmed-starters minutes source; minutes remain projections')
        if status=='projected' and mm!='projected_starters_projected_minutes':
            raise ValueError('projected lineup status requires projected-starters minutes source')
        trained_until = base._time(data.get('rating_model_source',{}).get('trained_until'),'rating_model_source.trained_until')
        if trained_until >= cutoff: raise ValueError('player strength model must be trained before cutoff')
        if data['rating_model_source'].get('method')!='independent_prior_player_ratings':
            raise ValueError('must use independently fitted pre-match player ratings')
        scale_id = data['rating_model_source'].get('scale_id')
        if not isinstance(scale_id,str) or not scale_id.strip():
            raise ValueError('rating_model_source.scale_id required for comparable player ratings')
        players = data.get('players')
        if not isinstance(players,list) or len(players)<11:
            raise ValueError('at least 11 potential players are required')
        ids=set(); expected_total=0; reference_total=0
        available_sum=0; reference_sum=0; by_role={}
        for player in players:
            if not isinstance(player,dict): raise ValueError('player must be dict')
            pid=player.get('id')
            if not isinstance(pid,str) or not pid or pid in ids:
                raise ValueError('player id must be unique and present')
            ids.add(pid)
            role=player.get('role')
            if role not in ROLES: raise ValueError(f'unsupported role {role}')
            rating=player.get('rating_0_100')
            expected=player.get('expected_minutes'); reference=player.get('reference_minutes')
            if (type(rating) not in (int,float) or not math.isfinite(rating) or rating<0 or rating>100):
                raise ValueError('rating_0_100 requires independently fitted 0-100 rating')
            for nm,m in (('expected_minutes',expected),('reference_minutes',reference)):
                if type(m) not in (int,float) or not math.isfinite(m) or m < 0 or m >90:
                    raise ValueError(f'{nm} must be between 0 and 90')
            if expected>0 and player.get('availability') == 'unavailable':
                raise ValueError('unavailable player has positive expected minutes')
            if player.get('availability') not in ('available','probable','unavailable'):
                raise ValueError('availability must be available/probable/unavailable')
            expected_total += expected; reference_total += reference
            available_sum += rating*expected; reference_sum+=rating*reference
            rec = by_role.setdefault(role, {'expected_minutes':0.0,'reference_minutes':0.0,
                                            'expected_rating_sum':0.0,'reference_rating_sum':0.0})
            rec['expected_minutes']+=expected;rec['reference_minutes']+=reference
            rec['expected_rating_sum']+=rating*expected; rec['reference_rating_sum']+=rating*reference
        if abs(expected_total-REQUIRED_MINUTES) > 1e-7 or abs(reference_total-REQUIRED_MINUTES)>1e-7:
            raise ValueError(f'{side}: both reference and expected minutes must add up to 990; missing/unknown minutes cannot silently become zero')
        if (by_role.get('goalkeeper',{}).get('expected_minutes',0)!=90 or
            by_role.get('goalkeeper',{}).get('reference_minutes',0)!=90):
            raise ValueError('90 goalkeeping minutes required for expected and reference teams')
        role_shifts={role:round((info['expected_rating_sum']-info['reference_rating_sum'])/990.0,4)
                     for role,info in by_role.items()}
        results[side] = {'status':status, 'baseline_quality':reference_sum/990.0,
                         'effective_quality':available_sum/990.0,
                         'quality_change':(available_sum-reference_sum)/990.0,
                         'role_contributions':role_shifts, 'player_count':len(players),
                         'minutes_source_id':minutes_source,'rating_model_source_id':model_source,
                         'rating_scale_id':scale_id}
    if results['home']['rating_scale_id']!=results['away']['rating_scale_id']:
        raise ValueError('opposing teams must use the same calibrated player rating scale; no cross-league raw rating comparisons')
    relative=results['home']['quality_change']-results['away']['quality_change']
    expected_gap=results['home']['effective_quality']-results['away']['effective_quality']
    baseline_gap=results['home']['baseline_quality']-results['away']['baseline_quality']
    return {'status':'CONFIRMED_BOTH' if all(results[s]['status']=='confirmed' for s in ('home','away')) else 'PROJECTED_AT_LEAST_ONE',
            'sides':results, 'relative_shift':relative,
            'effective_quality_home_minus_away':expected_gap,
            'reference_quality_home_minus_away':baseline_gap,
            'direction_signal':'HOME_RELATIVE_STRENGTH_UP' if relative>=DELTA_REVIEW_THRESHOLD else
                        'AWAY_RELATIVE_STRENGTH_UP' if relative<=-DELTA_REVIEW_THRESHOLD else 'NO_LARGE_RELATIVE_CHANGE',
            'numeric_probability_change':False,
            'interpretation':'Deviation from separately estimated historical reference XI, NOT absolute strength or a fitted WDL probability'}


def motivation_stakes(motivation: Any, cutoff: datetime) -> dict:
    """Stakes indicate incentive and style uncertainty, never automatic win boost."""
    if motivation is None:
        return {'status':'UNKNOWN_NO_CONTEXT', 'teams':{}, 'asymmetry':'UNKNOWN',
                'win_necessity_not_win_probability':True}
    if not isinstance(motivation,dict) or set(motivation)!= {'home','away'}:
        raise ValueError('motivation must have exactly home and away')
    results={}; source_ids=set()
    for side in ('home','away'):
        d=motivation[side]
        if not isinstance(d,dict):raise ValueError('motivation team must be dict')
        kind=d.get('competition_context'); stakes=d.get('stakes_type'); urgency=d.get('urgency')
        if kind not in CONTEXT or stakes not in STAKES or urgency not in URGENCY:
            raise ValueError('invalid competition/stakes/urgency')
        must=d.get('win_mathematically_necessary')
        if type(must) is not bool:raise ValueError('win_mathematically_necessary must be bool')
        sid,_=_dated_record(d.get('basis_source'), cutoff, f'{side}.basis_source',allowed_basis=BASIS)
        source_ids.add(sid)
        hard_basis = d['basis_source']['basis'] in ('official_table_and_rules','official_knockout_regulations')
        if must and not hard_basis: raise ValueError('must-win requires official mathematics/regulations, not manager quotes')
        if must and stakes in ('routine','unknown'): raise ValueError('must-win inconsistent with routine/unknown stakes')
        if urgency=='high' and not hard_basis:
            raise ValueError('high urgency requires objective official table/rules evidence')
        # Even official maths alone does not measure how much a team is able to win.
        results[side]={'competition_context':kind,'stakes_type':stakes,'urgency':urgency,
                       'win_mathematically_necessary':must, 'source_id':sid,
                       'objective_basis':hard_basis,
                       'next_fixture_days':d.get('next_fixture_days'),
                       'risk_comment':'Must-win increases incentives, not inferred match outcome probability' if must else None}
        days=d.get('next_fixture_days')
        if days is not None and (type(days) is not int or days<0 or days>60):
            raise ValueError('next_fixture_days must be int 0..60 or null')
        if days is not None:
            _dated_record(d.get('fixture_source'),cutoff,f'{side}.fixture_source',allowed_basis={'official_schedule'})
    # One official table may reliably establish BOTH teams' stakes, but counts as just one source family.
    asym='BOTH_HIGH' if all(results[s]['urgency']=='high' for s in ('home','away')) else (
        'HOME_HIGH_ONLY' if results['home']['urgency']=='high' and results['away']['urgency'] in ('low','medium') else
        'AWAY_HIGH_ONLY' if results['away']['urgency']=='high' and results['home']['urgency'] in ('low','medium') else
        'NO_CLEAR_STAKES_EDGE')
    return {'status':'VERIFIED_BOTH', 'shared_source_between_teams':len(source_ids)<2,
            'teams':results,'asymmetry':asym,'win_necessity_not_win_probability':True,
            'numeric_probability_change':False}


def inspect(packet: dict) -> dict:
    """Separate direction, capacity, incentives, and evidence-based grant review.

    Source confidence always survives into output. No post-hoc outcome changes.
    A high-urgency team with poor available personnel is a CONFLICT, not a strong single.
    """
    result=base.recommend(packet)  # Existing WDL / time / same-source / hard-lock gates.
    cutoff=_check_cutoff(packet)
    squad=effective_squad_strength(packet.get('squads'),cutoff)
    mot=motivation_stakes(packet.get('motivation'),cutoff)
    direction=result['raw_single']
    swing=squad['relative_shift']
    direction_adj = None if swing is None or direction=='平' else (swing if direction=='胜' else -swing)
    capacity_status='UNKNOWN' if direction_adj is None else (
        'ADVERSE_TO_RAW_DIRECTION' if direction_adj<=-DELTA_REVIEW_THRESHOLD else
        'SUPPORTS_RAW_DIRECTION' if direction_adj>=DELTA_REVIEW_THRESHOLD else 'NEUTRAL_NEAR_BASELINE')
    raw_side='home' if direction=='胜' else 'away' if direction=='负' else None
    pressure='UNKNOWN'
    if raw_side is not None and mot['teams']:
        own=mot['teams'][raw_side]; opposite=mot['teams']['away' if raw_side=='home' else 'home']
        if own['win_mathematically_necessary'] and opposite['urgency']=='low': pressure='RAW_DIRECTION_HIGH_STAKES'
        elif opposite['win_mathematically_necessary'] and own['urgency']=='low':pressure='OPPONENT_HIGH_STAKES'
        else:pressure='NO_SIMPLE_DIRECTIONAL_MOTIVATION'
    conflict=bool(pressure=='RAW_DIRECTION_HIGH_STAKES' and capacity_status=='ADVERSE_TO_RAW_DIRECTION')
    # Missing context does not erase raw Top1 or the hypothetical selection experiment.
    # It blocks only claims of full, evidence-verified recovery/core, which require real supporting observations.
    quality_complete = squad['status'] in ('CONFIRMED_BOTH','PROJECTED_AT_LEAST_ONE')
    mot_complete = mot['status']=='VERIFIED_BOTH'
    both_confirmed = squad['status']=='CONFIRMED_BOTH'
    # Eligibility is intentionally a research CONDITIONAL CHECK, not a wager or a probability adjustment.
    verified_recovery_context = bool(result['shadow_recovery_evidence_verified'] and quality_complete and mot_complete
                                   and capacity_status!='ADVERSE_TO_RAW_DIRECTION' and
                                   pressure!='OPPONENT_HIGH_STAKES' and not conflict)
    core_context = bool(result['shadow_core_evidence_review_pass'] and both_confirmed and mot_complete
                        and capacity_status!='ADVERSE_TO_RAW_DIRECTION' and
                        pressure!='OPPONENT_HIGH_STAKES' and not conflict)
    review_flags=[]
    if quality_complete:
        for side in ('home','away'):
            k=squad['sides'][side]['role_contributions'].get('goalkeeper',0.0)
            if k<=-0.75:review_flags.append(f'{side.upper()}_GOALKEEPER_REPLACEMENT_QUALITY_DROP_REVIEW')
    if mot['teams']:
        for side in ('home','away'):
            days=mot['teams'][side]['next_fixture_days']
            if days is not None and days <= 3:
                review_flags.append(f'{side.upper()}_SHORT_TURNAROUND_ROTATION_AND_MOTIVATION_TRADEOFF')
    if not quality_complete: review_flags.append('MISSING_EFFECTIVE_SQUAD_STRENGTH')
    if not mot_complete: review_flags.append('MISSING_OR_DEPENDENT_STAKES_EVIDENCE')
    if capacity_status=='ADVERSE_TO_RAW_DIRECTION':review_flags.append('ACTUAL_SQUAD_QUALITY_CONTRADICTS_RAW_DIRECTION')
    if pressure=='OPPONENT_HIGH_STAKES':review_flags.append('OPPONENT_OBJECTIVE_WIN_PRESSURE')
    if conflict:review_flags.append('HIGH_INTENT_BUT_LOWER_EFFECTIVE_CAPACITY')
    if quality_complete and not both_confirmed: review_flags.append('LINEUP_PROJECTED_NOT_CONFIRMED')
    if direction=='平': review_flags.append('DRAW_NOT_A_FUNCTION_OF_MOTIVATION_PARITY')
    return {**result,'version':VERSION, 'effective_squad_ESR':squad,'objective_stakes_MSI':mot,
            'raw_direction_capacity_alignment':capacity_status, 'raw_direction_stakes_context':pressure,
            'intent_capacity_conflict':conflict,
            'research_recovery_context_review_pass':verified_recovery_context,
            'research_core_context_review_pass':core_context,
            'audit_flags':review_flags,'formal_single_grant':None,'formal_core_grant':None,
            'unmodified_probabilities':result['outcome_probabilities_unchanged'],
            'probability_adjustment_applied':False,
            'notes':[
               'Urgency is not a win probability or a stand-alone favorable evidence family.',
               'Player minutes and role/position replacement are one correlated roster family, not independent votes.',
               'Rest/fixture congestion and a rotation-triggered lineup change are causally correlated; do not double count.',
               'AIC, ESR and motivation require independent precutoff attribution and out-of-time calibration before affecting outcome or grant.',
               'No automatic reversal, protection changes, or Production CORE grants.']}


def replay_development(rows: list[dict]) -> dict:
    """Score only rule eligibility and data readiness; actual results are never fed to inspect."""
    if not isinstance(rows,list) or not rows:raise ValueError('rows needed')
    records=[]
    for row in rows:
        if row.get('split')!='development':raise ValueError('development-only replay')
        pre=dict(row['prematch'])
        result=inspect(pre)
        records.append({'id':pre.get('id'), 'date':pre.get('date'),
                        'raw_single':result['raw_single'],
                        'research_probability_potential':result['shadow_potential_eligible'],
                        'structural_recovery':result['shadow_recovery_potential'],
                        'recovery_verified_by_context':result['research_recovery_context_review_pass'],
                        'core_verified_by_context':result['research_core_context_review_pass'],
                        'squad_data_status':result['effective_squad_ESR']['status'],
                        'motivation_data_status':result['objective_stakes_MSI']['status'],
                        'formal_grant':None})
    return {'version':VERSION,'n':len(records),
            'probability_potential':sum(x['research_probability_potential'] for x in records),
            'context_verified_recoveries':sum(x['recovery_verified_by_context'] for x in records),
            'context_verified_cores':sum(x['core_verified_by_context'] for x in records),
            'missing_roster_n':sum(x['squad_data_status']=='UNKNOWN_NO_PREMATCH_SQUAD_MATRIX' for x in records),
            'missing_stakes_n':sum(x['motivation_data_status']=='UNKNOWN_NO_CONTEXT' for x in records),
            'independent_gain':None, 'formal_grant':None,
            'warning':'Missing original precutoff squad/standings evidence; do not impute features or claim accurate outcomes.',
            'matches':records}
