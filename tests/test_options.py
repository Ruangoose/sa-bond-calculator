from datetime import date
from math import erf, erfc, sqrt

import pytest

from sabond import BONDS, black76, bond_option, norm_cdf, price, price_vol_from_yield_vol


def test_norm_cdf_against_erfc():
    for i in range(-800, 801):
        x = i / 100
        assert norm_cdf(x) == pytest.approx(0.5 * erfc(-x / sqrt(2)), rel=1e-13, abs=1e-15)


def test_black76_at_the_money():
    # F = K: call = put = F x (2N(s/2) - 1) = F x erf(s / (2 sqrt 2)), with s = vol x sqrt(t).
    b = black76(100, 100, 1.0, 0.2, "call")
    assert b.value == pytest.approx(100 * erf(0.2 / (2 * sqrt(2))), rel=1e-13)
    assert black76(100, 100, 1.0, 0.2, "put").value == pytest.approx(b.value, rel=1e-13)


@pytest.mark.parametrize("fwd, strike", [(99.0, 103.7), (99.0, 99.0), (99.0, 94.5)])
def test_put_call_parity(fwd, strike):
    c = black76(fwd, strike, 0.25, 0.13, "call")
    p = black76(fwd, strike, 0.25, 0.13, "put")
    assert c.value - p.value == pytest.approx(fwd - strike, abs=1e-12)
    assert c.delta - p.delta == pytest.approx(1, abs=1e-15)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_black76_greeks(kind):
    f, k, t, v, h = 98.99, 97.0, 0.25, 0.13, 1e-4
    b = black76(f, k, t, v, kind)
    val = lambda f=f, t=t, v=v: black76(f, k, t, v, kind).value  # noqa: E731
    assert b.delta == pytest.approx((val(f + h) - val(f - h)) / (2 * h), rel=1e-8)
    assert b.gamma == pytest.approx((val(f + h) - 2 * b.value + val(f - h)) / h**2, rel=1e-4)
    assert b.vega == pytest.approx((val(v=v + h) - val(v=v - h)) / (2 * h), rel=1e-6)
    assert b.theta == pytest.approx(-(val(t=t + h) - val(t=t - h)) / (2 * h), rel=1e-7)


def example(kind="call", strike=9.5, vol=0.11):
    # Illustrative inputs only.
    return bond_option(BONDS["R2035"], date(2026, 10, 20), date(2027, 2, 4), 9.4, strike, 7.25, vol, kind)


def test_bond_option_pieces():
    o = example()
    assert o.forward.spot_settle == date(2026, 10, 23)
    assert o.forward.delivery == date(2027, 2, 9)
    assert o.t == 107 / 365
    assert o.strike_aip == price(BONDS["R2035"], date(2027, 2, 9), 9.5).aip_r
    b = black76(o.forward.aip, o.strike_aip, o.t, 0.11)
    assert o.value == b.value
    assert o.premium == pytest.approx(b.value * 1000, rel=1e-15)
    assert o.vega == pytest.approx(b.vega * 10, rel=1e-15)
    assert o.theta == pytest.approx(b.theta / 365 * 1000, rel=1e-15)
    assert o.delta_nominal == pytest.approx(b.delta * 100_000, rel=1e-15)


def test_yield_vol_conversion():
    o = example()
    assert o.yield_vol == pytest.approx(o.price_vol / (o.forward_dmod * o.forward.ytm / 100), rel=1e-15)
    assert price_vol_from_yield_vol(o.yield_vol, o.forward_dmod, o.forward.ytm) == pytest.approx(0.11, rel=1e-14)


def test_calls_gain_when_yields_fall():
    lo = example(strike=9.5)
    hi = bond_option(BONDS["R2035"], date(2026, 10, 20), date(2027, 2, 4), 9.41, 9.5, 7.25, 0.11, "call")
    assert lo.yield_delta < 0
    # The yield delta is the premium change for a 1bp rise in the spot yield.
    assert hi.premium - lo.premium == pytest.approx(lo.yield_delta, rel=0.02)


def test_put_call_parity_per_contract():
    c, p = example("call"), example("put")
    assert c.premium - p.premium == pytest.approx((c.forward.aip - c.strike_aip) * 1000, abs=1e-8)
