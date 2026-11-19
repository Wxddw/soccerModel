"""Contract tests for additive R6.3.6 postmatch joint audit."""
import pytest
from postmatch_joint_audit_r636 import audit_joint_q


def sample():
    return [
        {"score":"0:0","probability":.1},
        {"score":"1:0","probability":.2},
        {"score":"2:0","probability":.3},
        {"score":"2:1","probability":.2},
        {"score":"3:0","probability":.2},
    ]


def test_signed_jc_minus_two_boundaries():
    out = audit_joint_q(sample(), -2)
    assert out["jc"] == pytest.approx({"让胜":.2,"让平":.3,"让负":.5})
    assert out["jc_exact_draw_margin"] == 2
    assert out["wdl"] == pytest.approx({"胜":.9,"平":.1,"负":0})
    assert out["margin_buckets"]["home_1"] == pytest.approx(.4)
    assert out["margin_buckets"]["home_2"] == pytest.approx(.3)
    assert out["margin_buckets"]["home_3plus"] == pytest.approx(.2)
    assert sum(out["goals"].values()) == pytest.approx(1)
    assert out["research_only"] is True and out["formal_grant"] is None


def test_no_line_means_no_jc_release():
    out = audit_joint_q(sample())
    assert out["jc"] is None and out["jc_exact_draw_margin"] is None


def test_zero_and_seven_plus_exact_buckets():
    out = audit_joint_q([
        {"score":"0:0","probability":.4},
        {"score":"4:3","probability":.6},
    ], 1)
    assert out["goals"]["0"] == pytest.approx(.4)
    assert out["goals"]["7+"] == pytest.approx(.6)
    assert out["jc"]["让胜"] == pytest.approx(1)


@pytest.mark.parametrize("rows", [
    [{"score":"0:0","probability":.3}],
    [{"score":"0:0","probability":.6},{"score":"0:0","probability":.4}],
    [{"score":"0:0","probability":-1.},{"score":"1:0","probability":2.}],
])
def test_bad_matrix_is_not_silently_fixed(rows):
    with pytest.raises(ValueError):
        audit_joint_q(rows)


@pytest.mark.parametrize("line",[-.5, -.75, True, 4, " -1 "])
def test_only_official_integer_jc_line(line):
    with pytest.raises(ValueError):
        audit_joint_q(sample(), line)
