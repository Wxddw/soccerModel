"""Conservation and high-score tail guard for archived 31x31 grids."""
import pytest
from htft_segment_archive_bridge_r636 import predict_archived_grid

def spec():
    return {
        'source_id':'synthetic-Q','calibration_id':'synthetic-history',
        'observed_at':'2026-11-20T10:00:00+08:00',
        'cutoff':'2026-11-20T10:05:00+08:00',
        'kickoff':'2026-11-20T20:00:00+08:00',
        'latest_training_result_observed_at':'2026-11-19T23:00:00+08:00',
        'home_xg':1.5,'away_xg':1.0,
        'home_shares':[.15]*3+[.55/3]*3,'away_shares':[.15]*3+[.55/3]*3,
        'state_factors':{'home_leading':1.,'home_trailing':1.,
                         'away_leading':1.,'away_trailing':1.},
    }

def grid():
    q=[[0.]*12 for _ in range(12)]
    q[0][0]=.5
    q[1][0]=.4999
    q[11][0]=.0001
    return q

def test_archived_high_score_tail_is_neutral_and_conserved():
    a=predict_archived_grid(grid(),spec())
    assert a['research_only'] is True and a['formal_grant'] is None
    assert a['neutral_tail_fallback_mass']==pytest.approx(.0001)
    assert sum(a['probabilities'].values())==pytest.approx(1)
    assert sum(a['probabilities'][x+'胜'] for x in ('胜','平','负'))==pytest.approx(.5)
    assert sum(a['probabilities'][x+'平'] for x in ('胜','平','负'))==pytest.approx(.5)
    assert sum(s['home_expected_goals'] for s in a['segments'])==pytest.approx(.5010)
    assert sum(s['away_expected_goals'] for s in a['segments'])==pytest.approx(0)

def test_large_outside_support_mass_blocks():
    q=grid()
    q[0][0]=.4
    q[1][0]=.4
    q[11][0]=.2
    with pytest.raises(ValueError,match='guard'):
        predict_archived_grid(q,spec())

def test_bad_input_and_incomplete_mass_block():
    q=grid();q[0][0]=.4
    with pytest.raises(ValueError):
        predict_archived_grid(q,spec())
    q=grid();q[0][0]=-1
    with pytest.raises(ValueError):
        predict_archived_grid(q,spec())
