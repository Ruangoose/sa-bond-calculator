from datetime import date

import pytest

from sabond import BONDS, bond_option, implied_yield, price
from sabond.strategies import STRATEGIES, Leg, payoff, strategy_legs, value_strategy

BOND = BONDS["R2035"]
TRADE, EXPIRY = date(2026, 10, 20), date(2027, 2, 4)
SPOT, CARRY, VOL = 9.4, 7.25, 0.08
DELIVERY = date(2027, 2, 9)


def run(legs, **kw):
    return value_strategy(BOND, TRADE, EXPIRY, SPOT, CARRY, VOL, legs, **kw)


def test_built_in_structures():
    assert set(STRATEGIES) == {"Call", "Put", "Call spread", "Put spread", "Risk reversal", "Straddle", "Strangle",
                               "Fence", "Butterfly"}
    legs = strategy_legs("Fence", 9.52)
    assert [(l.kind, l.side, l.strike_yield) for l in legs] == [("call", -1, 9.02), ("call", 1, 9.52), ("put", -1, 10.02)]


def test_legs_are_the_single_options_signed():
    legs = strategy_legs("Fence", 9.5)
    s = run(legs)
    singles = [bond_option(BOND, TRADE, EXPIRY, SPOT, l.strike_yield, CARRY, VOL, l.kind) for l in legs]
    for v, o, l in zip(s.legs, singles, legs):
        assert v.option.premium == o.premium
        assert v.premium == l.side * o.premium and v.vega == l.side * o.vega
    assert s.net_premium == pytest.approx(sum(l.side * o.premium for l, o in zip(legs, singles)), rel=1e-15)
    assert s.delta == pytest.approx(sum(l.side * o.delta for l, o in zip(legs, singles)), rel=1e-15)
    assert s.delta_nominal == pytest.approx(s.delta * 100_000, rel=1e-15)


def test_outright_call():
    s = run([Leg("call", 1, 1, 9.5)])
    o = s.legs[0].option
    assert s.max_loss == pytest.approx(-o.premium, rel=1e-12)
    assert s.max_profit is None  # uncapped as yields fall
    # Breakeven: the price at which the call's intrinsic value repays its premium.
    (be,) = s.breakevens
    assert be == implied_yield(BOND, DELIVERY, o.strike_aip + o.premium / 1000)
    assert payoff(s, BOND, 12.0) == pytest.approx(-o.premium, rel=1e-12)


def test_call_spread_is_capped_both_ways():
    s = run(strategy_legs("Call spread", 9.5))
    lo_k = min(v.option.strike_aip for v in s.legs)
    hi_k = max(v.option.strike_aip for v in s.legs)
    assert s.net_premium > 0
    assert s.max_profit == pytest.approx((hi_k - lo_k) * 1000 - s.net_premium, rel=1e-12)
    assert s.max_loss == pytest.approx(-s.net_premium, rel=1e-12)
    (be,) = s.breakevens
    assert be == implied_yield(BOND, DELIVERY, lo_k + s.net_premium / 1000)


def test_straddle_and_strangle_have_two_breakevens():
    for name in ("Straddle", "Strangle"):
        s = run(strategy_legs(name, 9.5))
        assert len(s.breakevens) == 2
        assert s.max_profit is None
        assert s.max_loss == pytest.approx(-s.net_premium, rel=1e-12)  # all the premium, between the strikes
        assert s.vega > 0 and s.theta < 0


def test_fence_caps_profit_but_not_loss():
    s = run(strategy_legs("Fence", 9.5))
    assert s.max_profit is not None and s.max_loss is None


def test_butterfly_is_capped_and_short_volatility():
    s = run(strategy_legs("Butterfly", 9.5))
    assert s.max_profit is not None and s.max_loss is not None
    assert s.net_premium < 0  # you receive premium
    assert s.vega < 0
    assert len(s.breakevens) == 2


def test_long_call_short_put_is_the_forward():
    # Same strike: at expiry the pair is worth the delivery price less the strike, whatever the yield.
    s = run([Leg("call", 1, 1, 9.5), Leg("put", -1, 1, 9.5)])
    k = s.legs[0].option.strike_aip
    for y in (8.0, 9.5, 11.0):
        p = price(BOND, DELIVERY, y).aip_r
        assert payoff(s, BOND, y) == pytest.approx((p - k) * 1000 - s.net_premium, rel=1e-12, abs=1e-9)


def test_ratio_scales_a_leg():
    one = run([Leg("call", -1, 1, 9.25)])
    two = run([Leg("call", -1, 2, 9.25)])
    assert two.net_premium == pytest.approx(2 * one.net_premium, rel=1e-15)
    assert two.gamma == pytest.approx(2 * one.gamma, rel=1e-15)
