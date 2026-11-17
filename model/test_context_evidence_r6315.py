import copy
import pytest
from context_evidence_r6315 import FACTORS, IN_PLAY_ONLY, audit

def p(obs=None):
    return {'cutoff':'2026-11-16T12:00:00+08:00',
            'kickoff':'2026-11-17T03:45:00+08:00',
            'observations': [] if obs is None else obs}

def item(factor='injury_suspension', **kwargs):
    o={'factor':factor,'value':-0.7,
       'evidence_asof':'2026-11-16T11:00:00+08:00',
       'source_url':'https://example.org/team-official','source_family':'team_report',
       'confidence':.95,'availability':'confirmed'}
    o.update(kwargs);return o

def test_empty_safe():
    r=audit(p());assert r['status']=='RESEARCH_EVIDENCE_ONLY';assert not r['change_production']
    assert r['automatic_model_weights'] is None and r['eligible_factors']==[]

def test_valid():
    x=p([item()]);before=copy.deepcopy(x);r=audit(x)
    assert x==before and r['coverage']['eligible']==1 and len(r['accepted'])==1

@pytest.mark.parametrize('factor',sorted(FACTORS))
def test_each_prematch_factor_allowed_as_evidence(factor):
    assert factor in audit(p([item(factor)]))['eligible_factors']

@pytest.mark.parametrize('factor',sorted(IN_PLAY_ONLY))
def test_realized_outcomes_are_blocked(factor):
    assert audit(p([item(factor)]))['blocked'][0]['reason']=='IN_PLAY_OR_POSTMATCH_FORBIDDEN'

@pytest.mark.parametrize('timestamp', ['2026-11-16T12:01:00+08:00','2026-11-17T03:46:00+08:00'])
def test_future_evidence_blocked(timestamp):
    assert audit(p([item(evidence_asof=timestamp)]))['blocked'][0]['reason']=='FUTURE_OR_POST_CUTOFF'

def test_double_count_family_blocked():
    r=audit(p([item(),item(source_url='https://another.site/republish')]))
    assert len(r['accepted'])==1 and r['blocked'][0]['reason']=='DUPLICATE_EVIDENCE_FAMILY'

def test_other_family_allowed():
    r=audit(p([item(),item(source_family='independent_coach_press_conference')]))
    assert len(r['accepted'])==2 and r['distinct_evidence_families']==2

@pytest.mark.parametrize('value', [float('nan'),float('inf'),2,True])
def test_bad_value_rejected(value):
    with pytest.raises(ValueError):audit(p([item(value=value)]))

@pytest.mark.parametrize('confidence', [-.2,1.4,float('nan')])
def test_bad_confidence_rejected(confidence):
    with pytest.raises(ValueError):audit(p([item(confidence=confidence)]))

def test_no_source_blocked():
    assert audit(p([item(source_url='local-file')]))['blocked'][0]['reason']=='MISSING_AUTHORITATIVE_SOURCE'

def test_unavailable_blocked():
    assert audit(p([item(availability='unavailable')]))['blocked'][0]['reason']=='NOT_AVAILABLE_PREMATCH'

def test_cutoff_must_precede_kickoff():
    x=p();x['cutoff']=x['kickoff']
    with pytest.raises(ValueError):audit(x)

def test_no_hidden_actual_score():
    x=p();x['actual_score']='3:2'
    with pytest.raises(ValueError):audit(x)

def test_naive_time_rejected():
    with pytest.raises(ValueError):audit(p([item(evidence_asof='2026-11-16T11:00:00')]))

def test_unknown_factor_rejected():
    with pytest.raises(ValueError):audit(p([item('postmatch_goalkeeper_saves')]))

def test_unexpected_fields_rejected():
    x=item();x['actual_red_card']=1
    with pytest.raises(ValueError):audit(p([x]))

def test_expected_not_confirmed():
    r=audit(p([item(availability='expected')]))
    assert not r['accepted'][0]['confirmed']

def test_timezone_conversion():
    r=audit(p([item(evidence_asof='2026-11-16T03:00:00Z')]))
    assert r['accepted'][0]['asof']=='2026-11-16T03:00:00+00:00'

def test_absolute_grants_prohibited():
    r=audit(p([item(),item('motivation_pressure',source_family='independent_press')]))
    assert r['allow_core_grant'] is False and r['allow_outcome_reversal'] is False
    assert r['forward_validation_certified'] is False
