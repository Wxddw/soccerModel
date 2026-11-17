"""Shadow R6.3.3: selection accuracy / coverage trade-off diagnostics.

Research-only selection overlay for archived *pre-match* W/D/L probabilities.
Does not fit weights, change probabilities, modify M79.3.6 Production, or grant
real-money recommendations. Actual scores are accepted only by paired_audit,
never by recommend().
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

VERSION = 'M79.3.6_SHADOW_R6.3.3_20261104'
CHOICES = ('胜', '平', '负')
# PREDECLARED research-only controls; not trained / not endorsed for production.
CONTROLS = {
    'reference_min_top1': .50, 'reference_min_gap': .05,
    'research_recovery_min_top1': .42, 'research_recovery_max_top1_exclusive': .50,
    'research_recovery_min_gap': .12,
    'core_candidate_min_top1': .65, 'core_candidate_min_gap': .25,
    'near_tie_gap': .05,
}


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{label} requires timezone-aware ISO timestamp')
    try: d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as e: raise ValueError(f'{label} invalid ISO timestamp') from e
    if d.utcoffset() is None: raise ValueError(f'{label} requires timezone')
    return d


def _p3(value: Any) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('probabilities must be [home_win, draw, away_win]')
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1 for x in value):
        raise ValueError('probabilities must be finite within [0,1]')
    p = tuple(float(x) for x in value)
    if not math.isclose(sum(p), 1.0, abs_tol=.002):
        raise ValueError('probabilities do not sum to 1 (0.2 percentage-point tolerance for rounded archive)')
    return tuple(v / sum(p) for v in p)


def _evidence(packet: dict, cutoff: datetime) -> dict:
    """Evidence families cannot be supplied by outcome/score results or postcutoff events.

    The absence of evidence is UNKNOWN, not evidence of absence of risk.
    """
    allowed = {'team_news', 'market_price', 'market_funds', 'schedule', 'tactics', 'official_lineup'}
    decisions: dict[str, str] = {}
    canonical_family = {'market_price':'market','market_funds':'market',
                        'team_news':'roster','official_lineup':'roster',
                        'schedule':'schedule','tactics':'tactics'}
    invalid: list[str] = []
    evidence = packet.get('evidence', [])
    if not isinstance(evidence, list): raise ValueError('evidence must be list')
    for rec in evidence:
        if not isinstance(rec, dict): raise ValueError('evidence item must be object')
        family = rec.get('family')
        if family not in allowed: raise ValueError('unsupported evidence family')
        group = canonical_family[family]
        if group in decisions: raise ValueError('duplicate correlated evidence group; reconcile before counting')
        if not isinstance(rec.get('source_id'), str) or not rec['source_id'].strip():
            raise ValueError('evidence source_id required')
        observed = _time(rec.get('observed_at'), 'evidence.observed_at')
        if observed > cutoff: raise ValueError('future/post-cutoff evidence not allowed')
        state = rec.get('state')
        if state not in ('favorable', 'neutral', 'adverse'):
            raise ValueError('state must be favorable / neutral / adverse')
        decisions[group] = state
    n_good = sum(x == 'favorable' for x in decisions.values())
    n_bad = sum(x == 'adverse' for x in decisions.values())
    # Market price, Kelly, bookmaker moves all share one market-price family.
    return {'families': decisions, 'favorable_families': n_good, 'adverse_families': n_bad,
            'independent_families_n': len(decisions), 'evidence_complete': len(decisions) >= 2,
            'source_audit_failures': invalid}


def recommend(packet: dict) -> dict:
    """Pre-match only: labels direction, potential Shadow recovery, and core review.

    Potential recovery NEVER equals an actual execution grant. Core requires two
    independently sourced favorable families and no verified adverse family;
    even then output is only a research candidate requiring independent calibration.
    """
    # Fail closed on explicit or nested retrospective fields anywhere in input.
    illegal = {'actual_score', 'result', 'actual_result', 'score_90', 'ft_score', 'final_score',
               'scoreline', 'red_card', 'inplay_event', 'post_match', 'match_result',
               'actual_margin', 'half_time_actual'}
    def scan(v: Any):
        if isinstance(v, dict):
            for k, x in v.items():
                if str(k).lower() in illegal: raise ValueError(f'post-match field not allowed: {k}')
                scan(x)
        elif isinstance(v, list):
            for x in v: scan(x)
    scan(packet)
    cutoff = _time(packet.get('cutoff'), 'cutoff')
    kickoff = _time(packet.get('kickoff'), 'kickoff')
    if cutoff >= kickoff: raise ValueError('cutoff must precede kickoff')
    p = _p3(packet.get('probabilities'))
    ranked = sorted(range(3), key=lambda i: (-p[i], i))
    best, second = ranked[:2]
    top1, gap = p[best], p[best] - p[second]
    raw = CHOICES[best]
    open_for_ordinary = packet.get('ordinary_sale') is True
    if type(packet.get('ordinary_sale')) is not bool:
        raise ValueError('ordinary_sale must be an explicit boolean')
    ev = _evidence(packet, cutoff)
    frozen_single = packet.get('frozen_single')
    frozen_pair = packet.get('frozen_protection')
    if frozen_single is not None and frozen_single not in CHOICES:
        raise ValueError('invalid frozen_single')
    if frozen_pair is not None:
        if not isinstance(frozen_pair, list) or len(frozen_pair) != 2 or len(set(frozen_pair)) != 2 or not set(frozen_pair).issubset(CHOICES):
            raise ValueError('frozen_protection must be exactly two distinct WDL choices')
        if frozen_single is None or frozen_single not in frozen_pair:
            raise ValueError('protection mismatch: fail closed; no auto repair')
    direction_conflict = frozen_single is not None and frozen_single != raw
    ref = open_for_ordinary and top1 >= CONTROLS['reference_min_top1'] and gap >= CONTROLS['reference_min_gap']
    recovery = (open_for_ordinary and CONTROLS['research_recovery_min_top1'] <= top1
                < CONTROLS['research_recovery_max_top1_exclusive'] and gap >= CONTROLS['research_recovery_min_gap'])
    if direction_conflict:
        status = 'HOLD_FROZEN_DIRECTION_CONFLICT_NO_AUTO_FLIP'
    elif not open_for_ordinary:
        status = 'UNAVAILABLE_ORDINARY'
    elif top1 < .4:
        status = 'BLOCK_LT40'
    elif ref:
        status = 'REFERENCE_OBSERVATION_ONLY'
    elif recovery:
        status = 'SHADOW_POTENTIAL_RECOVERY_REVIEW'
    elif top1 < .5:
        status = 'WFC_WATCH_NO_GRANT'
    else:
        status = 'NCG_NARROW_GAP_REVIEW'
    # Two or more independent adverse prematch signal families block a recovery; one adverse requires review.
    adverse_block = ev['adverse_families'] >= 2
    if adverse_block and status in ('REFERENCE_OBSERVATION_ONLY', 'SHADOW_POTENTIAL_RECOVERY_REVIEW'):
        status = 'SHADOW_TWO_INDEPENDENT_ADVERSE_REVIEW_BLOCK'
    candidate = bool((ref or recovery) and not adverse_block and not direction_conflict)
    verified_recovery = bool(recovery and not adverse_block and not direction_conflict
                             and ev['independent_families_n'] >= 2
                             and ev['favorable_families'] >= 1
                             and ev['adverse_families'] == 0)
    # Research-only core candidate; no formal CORE grant without out-of-time calibration.
    core_structural = (open_for_ordinary and not direction_conflict
                       and top1 >= CONTROLS['core_candidate_min_top1']
                       and gap >= CONTROLS['core_candidate_min_gap'])
    core_review = bool(core_structural and ev['favorable_families'] >= 2 and ev['adverse_families'] == 0)
    proposed_protection = [CHOICES[i] for i in ranked[:2]]
    return {
        'version': VERSION, 'id': str(packet.get('id', '')), 'cutoff': packet['cutoff'],
        'raw_single': raw, 'raw_top1': top1, 'gap': gap,
        'frozen_single_unchanged': frozen_single, 'frozen_protection_unchanged': frozen_pair,
        'research_proposed_protection': proposed_protection, 'direction_conflict': direction_conflict,
        'ordinary_sale': open_for_ordinary, 'reference_proxy_eligible': ref,
        'shadow_potential_eligible': candidate,
        'shadow_recovery_potential': bool(recovery and not adverse_block),
        'shadow_recovery_evidence_verified': verified_recovery,
        'shadow_core_structural_potential': core_structural,
        'shadow_core_evidence_review_pass': core_review,
        'outcome_probabilities_unchanged': list(p), 'evidence_audit': ev,
        'status': status, 'formal_single_grant': None, 'formal_core_grant': None,
        'production_changed': False,
    }


def paired_audit(rows: list[dict]) -> dict:
    """Descriptive, same-input paired scoring; not independent validation.

    `rows`: [{"prematch": {...}, "actual_score": [h,a], "split":"development"}].
    Identical probabilities imply exact zero change in proper probability scores.
    """
    if not rows: raise ValueError('non-empty paired rows required')
    per = []; seen = set()
    for row in rows:
        if row.get('split') != 'development':
            raise ValueError('this diagnostic accepts development only; no holdout claims')
        pre = row['prematch']
        rid = (str(pre.get('date')), str(pre.get('id')))
        if rid in seen: raise ValueError('duplicate date + id')
        seen.add(rid)
        out = recommend(pre)
        score = row.get('actual_score')
        if (not isinstance(score, list) or len(score) != 2 or
            any(type(x) is not int or x < 0 for x in score)):
            raise ValueError('actual_score must be 90-minute [home,away] integers')
        actual_i = 0 if score[0] > score[1] else 1 if score[0] == score[1] else 2
        actual = CHOICES[actual_i]
        p = out['outcome_probabilities_unchanged']
        brier = sum((q - float(i == actual_i))**2 for i,q in enumerate(p))
        logloss = -math.log(max(p[actual_i],1e-15))
        per.append({**out,'date':pre.get('date'), 'actual':actual, 'raw_hit':out['raw_single']==actual,
                    'brier':brier,'logloss':logloss})
    sale = [x for x in per if x['ordinary_sale']]
    def summary(rows: list[dict], prop: str) -> dict:
        picked = [x for x in rows if x[prop]]
        good = [x for x in picked if x['raw_hit']]
        killed = [x for x in rows if not x[prop] and x['raw_hit']]
        return {'n':len(rows),'selected':len(picked),'hits':len(good),
                'misses':len(picked)-len(good), 'coverage':len(picked)/len(rows) if rows else None,
                'conditional_accuracy':len(good)/len(picked) if picked else None,
                'correct_top1_not_selected':len(killed),
                'correct_top1_not_selected_ids':[f"{x['date']}-{x['id']}" for x in killed]}
    reference = summary(sale, 'reference_proxy_eligible')
    shadow = summary(sale, 'shadow_potential_eligible')
    recovered = [x for x in sale if x['shadow_potential_eligible'] and not x['reference_proxy_eligible']]
    return {'version': VERSION, 'population':'ordinary OPEN only; different snap precision across days',
            'n_all':len(per), 'n_sale':len(sale),
            'reference_observation_proxy':reference,
            'shadow_probability_only_potential':shadow,
            'recovery_n':len(recovered),
            'recovery_hits':sum(x['raw_hit'] for x in recovered),
            'recovery_misses':sum(not x['raw_hit'] for x in recovered),
            'recoveries':[{'match':f"{x['date']}-{x['id']}", 'direction':x['raw_single'],
                           'p':round(x['raw_top1'],4),'gap':round(x['gap'],4),
                           'actual':x['actual'],'hit':x['raw_hit'],
                           'evidence_verified':x['shadow_recovery_evidence_verified']} for x in recovered],
            'raw_top1_hits_all':sum(x['raw_hit'] for x in per),
            'raw_top1_hits_sale':sum(x['raw_hit'] for x in sale),
            'unselected_correct_reference':reference['correct_top1_not_selected'],
            'unselected_correct_shadow':shadow['correct_top1_not_selected'],
            'mean_brier_reference':sum(x['brier'] for x in sale)/len(sale) if sale else None,
            'mean_brier_shadow':sum(x['brier'] for x in sale)/len(sale) if sale else None,
            'mean_logloss_reference':sum(x['logloss'] for x in sale)/len(sale) if sale else None,
            'mean_logloss_shadow':sum(x['logloss'] for x in sale)/len(sale) if sale else None,
            'core_structural_opportunities':sum(x['shadow_core_structural_potential'] for x in sale),
            'core_evidence_verified':sum(x['shadow_core_evidence_review_pass'] for x in sale),
            'formal_grant_count':None,
            'independent_forward_improvement':None,
            'status':'DEVELOPMENT_ONLY_NO_FORMAL_PERFORMANCE_CLAIM',
            'notes': ['The reference is a reconstructed observation threshold, NOT logged M79 Production grants.',
                      'Shadow potential selection ignores missing evidence and is NOT an actionable single.',
                      'Every match retains the same WDL probabilities. Proper scoring changes exactly zero.',
                      'Historical outcome labels are joined only after the pre-match decision is computed.',
                      'No selection threshold was fitted to these scores. Do not call this an independent holdout.'],
            'rows': per}
