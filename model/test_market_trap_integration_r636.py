import copy
import pytest
from test_matchday_publish_gate_r636 import pkt
from market_trap_integration_r636 import prematch_audit_with_market
from market_trap_cold_watch_r636 import no_historical_market_packet

def test_integration_neutral_with_missing_market_history():
    p=pkt(); b=copy.deepcopy(p)
    m=no_historical_market_packet(p['match_id'],p['cutoff'],p['kickoff'],p['official_jc_line'])
    old=copy.deepcopy(m)
    a=prematch_audit_with_market(p,m)
    assert a['market']['status']=='INSUFFICIENT_BOOKMAKER_TIME_SERIES'
    assert a['existing_exposure']['original_wdl_selection_unchanged']==p['frozen_wdl']
    assert not a['market_can_authorize_auto_reversal'] and not a['production_mutated']
    assert p==b and m==old

def test_mismatched_jc_line_rejected():
    p=pkt();m=no_historical_market_packet(p['match_id'],p['cutoff'],p['kickoff'],-2)
    with pytest.raises(ValueError):prematch_audit_with_market(p,m)

def test_mismatched_cutoff_rejected():
    p=pkt();m=no_historical_market_packet(p['match_id'],'2026-11-21T00:00:00+08:00',p['kickoff'],p['official_jc_line'])
    with pytest.raises(ValueError):prematch_audit_with_market(p,m)