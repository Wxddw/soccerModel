import copy
from datetime import datetime, timedelta, timezone
import pytest
from market_trap_cold_watch_r636 import screen, no_historical_market_packet

CUT='2026-11-23T13:30:00+08:00'
START='2026-11-23T05:00:00+08:00'
END='2026-11-23T12:00:00+08:00'
KICK='2026-11-24T02:00:00+08:00'

def q(book,market,odds,dt,line=None):
    return {'bookmaker':book,'market':market,'observed_at':dt,'source_url':'https://odds.example.org/'+book,
            'odds':odds,'line_home':line if market=='asian' else None,'line_goals':None}

def base():
    x=no_historical_market_packet('fixture-1',CUT,KICK,-1)
    x['quotes']=[q('a','1x2',[1.35,5.0,9.0],START),q('a','1x2',[1.55,4.5,7.0],END),
                 q('b','1x2',[1.36,5.1,8.7],START),q('b','1x2',[1.54,4.4,7.1],END)]
    return x

def test_empty_data_fail_closed():
    x=no_historical_market_packet('id',CUT,KICK,-3)
    o=screen(x);assert o['status']=='INSUFFICIENT_BOOKMAKER_TIME_SERIES' and o['flags']==[]
    assert not o['intent_proven'] and not o['auto_flip_wdl']

def test_one_book_not_market_consensus():
    x=base();x['quotes']=x['quotes'][:2]
    assert screen(x)['status']=='INSUFFICIENT_BOOKMAKER_TIME_SERIES'

def test_market_drifts_against_favorite():
    o=screen(base());assert o['european_1x2_two_or_more_paired_books']
    assert 'FAVORITE_PROBABILITY_DRIFT_REVIEW_ONLY' in o['flags']
    assert not o['auto_change_q']

def test_crowd_contradiction_only_with_pregame_stamp():
    x=base();x['crowd']={'observed_at':END,'source_id':'crowd-a','share_home':.8,'share_draw':.1,'share_away':.1}
    assert 'CROWD_HEAT_VS_MARKET_DRIFT_REVIEW_ONLY' in screen(x)['flags']
    x['crowd']['observed_at']='2026-11-24T03:00:00+08:00'
    with pytest.raises(ValueError):screen(x)

def test_euro_asian_opposite_movement():
    x=base()
    # Make WDL home strong increase, AH weakens -1 to -0.5, across two books.
    x['quotes'][1]['odds']=[1.21,6,11];x['quotes'][3]['odds']=[1.22,6.1,10.6]
    for b in ('a','b'):
        x['quotes'] += [q(b,'asian',[1.9,1.9],START,-1.),q(b,'asian',[1.9,1.9],END,-.5)]
    out=screen(x)
    assert 'EURO_ASIAN_OPPOSITE_MOVES_REVIEW_ONLY' in out['flags']
    assert out['official_jc_signed_line']==-1

def test_cold_bookmaker_move_and_independent_sources():
    x=base()
    # Underdog is initially much lower. Later both books shorten it.
    x['quotes'][1]['odds']=[1.37,5.,5.0];x['quotes'][3]['odds']=[1.38,5.,5.1]
    x['independent_evidence']=[
        {'family':'roster','side':'home','impact':'adverse','source_id':'injury-news','observed_at':END},
        {'family':'tactics','side':'away','impact':'favorable','source_id':'coach-report','observed_at':END}]
    o=screen(x)
    assert 'UNDERDOG_PRICE_SHORTENING_COLD_WATCH_ONLY' in o['flags']
    assert 'COLD_SIDE_WITH_TWO_NONMARKET_FAMILIES_SECOND_REVIEW' in o['flags']
    assert not o['auto_flip_wdl']

def test_same_source_not_two_independent_supporters():
    x=base();x['quotes'][1]['odds']=[1.37,5.,5.0];x['quotes'][3]['odds']=[1.38,5.,5.1]
    x['independent_evidence']=[
        {'family':'roster','side':'home','impact':'adverse','source_id':'same-story','observed_at':END},
        {'family':'tactics','side':'away','impact':'favorable','source_id':'same-story','observed_at':END}]
    assert not screen(x)['nonmarket_independent_support']

def test_postcutoff_market_blocked():
    x=base();x['quotes'][3]['observed_at']='2026-11-24T01:00:00+08:00'
    with pytest.raises(ValueError):screen(x)

def test_result_schema_blocked():
    x=base();x['actual_score']='1:1'
    with pytest.raises(ValueError):screen(x)

def test_jc_2_only_integer_and_asian_quarters():
    x=base();x['official_jc_signed_line']=-.5
    with pytest.raises(ValueError):screen(x)
    x=base();x['quotes'].append(q('a','asian',[1.90,1.90],START,-.75))
    o=screen(x);assert o['official_jc_signed_line']==-1

def test_corrupt_odds_rejected():
    x=base();x['quotes'][0]['odds']=[-1,5,9]
    with pytest.raises(ValueError):screen(x)

def test_duplicate_book_time_rejected():
    x=base();x['quotes'].append(copy.deepcopy(x['quotes'][0]))
    with pytest.raises(ValueError):screen(x)

def test_no_crowd_signal_when_absent():
    assert 'CROWD_HEAT_VS_MARKET_DRIFT_REVIEW_ONLY' not in screen(base())['flags']

def test_source_input_unchanged():
    x=base();before=copy.deepcopy(x);screen(x)
    assert x==before

def test_source_sha_stable():
    x=base();assert screen(x)['source_sha256']==screen(x)['source_sha256']

def test_no_missing_book_inference_from_single_snapshot():
    x=no_historical_market_packet('foo',CUT,KICK,-1)
    x['quotes']=[q('a','asian',[1.9,1.9],START,-.25),q('b','asian',[1.9,1.9],START,-.25)]
    assert screen(x)['status']=='INSUFFICIENT_BOOKMAKER_TIME_SERIES'