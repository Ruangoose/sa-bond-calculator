"""The two worked examples in the JSE's Bond Pricing Formula specification (BESA, 24 August 2005).

Example 1 prices R1,500,000 nominal of R186 at a yield of 7.5% for settlement on 26 August 2005.
Example 2 finds the implied yield of R186 from an all-in price of 95.123456789 on the same date.

The document prints most intermediate values to 15 significant figures (marked with an ellipsis).
Those are compared to a relative 1e-13; rounded results (prices, considerations, the implied yield)
are compared exactly.
"""

from datetime import date

import pytest

from sabond import Bond, implied_yield, price

# R186 as the example reads it from "a database of bonds". The bond itself was split into R187 and
# R188 in December 2025, so it isn't in the package's bond list.
R186 = Bond(
    code="R186",
    coupon=10.5,
    maturity=date(2026, 12, 21),
    coupon_dates=((21, 6), (21, 12)),
    books_closed=((11, 6), (11, 12)),
)

SETTLE = date(2005, 8, 26)


def sig(x, n=15):
    """x to n significant figures, as the document displays it."""
    return float(f"{x:.{n - 1}e}")


@pytest.fixture(scope="module")
def ex1():
    return price(R186, SETTLE, 7.5, nominal=1_500_000)


def test_timing(ex1):
    assert ex1.lcd == date(2005, 6, 21)
    assert ex1.ncd == date(2005, 12, 21)
    assert ex1.bcd == date(2005, 12, 11)
    assert ex1.n == 42
    assert ex1.cumex == 1
    assert ex1.days_acc == 66
    assert ex1.cpn == 5.25
    assert ex1.cpn_ncd == 5.25


@pytest.mark.parametrize(
    "field, printed",
    [
        ("f", 0.963855421686747),
        ("bp", 0.639344262295082),
        ("bpf", 0.97673802761755),
        ("dbpf", 0.647889548237297),
        ("d2bpf", -0.242427523582234),
        ("accrint", 1.8986301369863),
        ("aip", 133.547091364729),
        ("cp", 131.648461227743),
        ("dcpn", 1862.62309856317),
        ("d2cpn", 45079.3564011142),
        ("dr", 928.403928848386),
        ("d2r", 39491.9821233882),
        ("daip", 2814.68664663936),
        ("d2aip", 86187.4503185668),
        ("delta", -13.0744625769284),
        ("dmod", 9.79015150634829),
        ("dur", 10.1572821878364),
        ("d2aip_dy2", 1.98567065431985),
        ("conv", 148.686926388895),
    ],
)
def test_intermediate_values(ex1, field, printed):
    # The document shows 15 significant figures; a few values differ from ours in the 15th, which
    # is floating-point noise from the order of operations. Agreement to 1e-13 is 13 figures.
    assert getattr(ex1, field) == pytest.approx(printed, rel=1e-13, abs=0)


def test_rounded_results(ex1):
    assert ex1.accrint_r == 1.89863
    assert ex1.cp_r == 131.64846
    assert ex1.aip_r == 133.54709


def test_considerations(ex1):
    assert ex1.int_consid == 28_479.45
    assert ex1.allin_consid == 2_003_206.35
    assert ex1.clean_consid == 1_974_726.90


def test_rands_per_point(ex1):
    # Printed as "R 1,307.45 ..." per R1m nominal, sign dropped.
    assert round(ex1.rands_per_point, 2) == 1307.45


def matches(value, printed):
    """True if value shows as the printed string, to as many significant figures as it has."""
    digits = len(printed.replace("-", "").replace(".", "").lstrip("0"))
    return sig(value, digits) == sig(float(printed), digits)


def test_example_2_implied_yield():
    result = implied_yield(R186, SETTLE, 95.123456789, trace=True)
    assert result.yield_ == 11.34459
    # The iteration table, one column per iteration.
    table = {
        "y": ["10", "11.34241977", "11.34459412"],
        "f": ["0.9523809524", "0.94633155152", "0.94632181550"],
        "aip": ["106.23956578", "95.13982801", "95.12345679"],
        "daip": ["1998.7921662", "1681.7404217", "1681.2806705"],
        "d2aip": ["57984.112556", "47229.418148", "47213.938653"],
        "diff": ["11.116108994", "0.016371219"],
        "next_f": ["0.946331552", "0.946321816", "0.946321816"],
        "next_y": ["11.34241977", "11.34459412", "11.34459412"],
    }
    assert len(result.steps) == 3
    for field, row in table.items():
        for step, printed in zip(result.steps, row):
            assert matches(getattr(step, field), printed), (field, getattr(step, field), printed)
    # The third diff prints as 0.0000000001: the target is met to about 1e-10.
    assert abs(result.steps[2].diff) < 5e-10
    assert [step.prev for step in result.steps] == [10.0, 11.34242, 11.34459]
    assert [step.opp for step in result.steps] == [12.68484, 11.34677, 11.34459]
