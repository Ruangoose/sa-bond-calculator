"""The JSE formula's conventions, checked across every bond in the list."""

from datetime import date, timedelta

import pytest

from sabond import BONDS, implied_yield, price, timing
from sabond.jse import _on


def settlement_dates(bond, start=date(2026, 10, 20), step=11):
    d = start
    while d < bond.maturity:
        yield d
        d += timedelta(days=step)


def coupon_schedule(bond):
    dates = []
    for y in range(2000, bond.maturity.year + 1):
        for dm in bond.coupon_dates:
            c = _on(y, dm)
            if c <= bond.maturity:
                dates.append(c)
    return sorted(dates)


@pytest.mark.parametrize("code", BONDS)
def test_n_counts_the_remaining_coupons(code):
    bond = BONDS[code]
    schedule = coupon_schedule(bond)
    for s in settlement_dates(bond):
        t = timing(bond, s)
        assert t.lcd in schedule and t.ncd in schedule
        assert t.lcd <= s < t.ncd
        assert t.n == sum(1 for c in schedule if c > t.ncd)


def test_bond_terms():
    for bond in BONDS.values():
        assert (bond.maturity.day, bond.maturity.month) in bond.coupon_dates
        for (cd, cm), (bd, bm) in zip(bond.coupon_dates, bond.books_closed):
            paid = date(2026, cm, cd)
            closed = date(2026, bm, bd)
            assert (paid - closed).days == 10
    assert BONDS["R2030"].coupon_dates == ((31, 1), (31, 7))


def test_cum_and_ex_interest():
    bond = BONDS["R2035"]  # coupons 28 Feb and 31 Aug, books close 18 Feb and 21 Aug
    cum = price(bond, date(2027, 2, 17), 9.0)
    ex = price(bond, date(2027, 2, 18), 9.0)
    assert cum.cumex == 1 and cum.days_acc == (date(2027, 2, 17) - date(2026, 8, 31)).days
    assert ex.cumex == 0 and ex.days_acc == -10
    assert ex.accrint_r == round(-10 * 8.875 / 365, 5)
    # The all-in price drops by about the coupon; the clean price moves only a little. It does move:
    # accrued interest is actual/365, so 180 days' accrual isn't quite half a coupon (here 2.5c),
    # one of the formula's known anomalies.
    assert cum.aip_r - ex.aip_r == pytest.approx(8.875 / 2, abs=0.05)
    assert abs(cum.cp_r - ex.cp_r) < 0.05


def test_settlement_on_a_coupon_date():
    bond = BONDS["R2040"]
    p = price(bond, date(2027, 1, 31), 9.0)
    assert p.lcd == date(2027, 1, 31) and p.ncd == date(2027, 7, 31)
    assert p.days_acc == 0 and p.accrint == 0
    # At its own coupon rate on a coupon date, a bond is worth exactly par.
    assert p.aip == pytest.approx(100, abs=1e-12)
    assert p.aip_r == 100.0


def test_february_28_in_a_leap_year():
    bond = BONDS["R2048"]
    t = timing(bond, date(2028, 2, 29))
    assert t.lcd == date(2028, 2, 28) and t.ncd == date(2028, 8, 31)


def test_last_coupon_period_is_priced_as_money_market():
    # Appendix, section 2: AIP = (100 + e.g/2) / (1 + d1/365 x i/100).
    bond = BONDS["R188"]
    for s, y in [(date(2027, 7, 1), 7.3), (date(2027, 12, 13), 6.8), (date(2027, 6, 21), 7.0)]:
        p = price(bond, s, y)
        assert p.n == 0
        d1 = (p.ncd - s).days
        expected = (100 + p.cumex * bond.coupon / 2) / (1 + d1 / 365 * y / 100)
        assert p.aip == pytest.approx(expected, rel=1e-14)


@pytest.mark.parametrize("code", BONDS)
def test_price_to_yield_round_trip(code):
    bond = BONDS[code]
    for s in list(settlement_dates(bond, step=97))[:12]:
        for y in (0.5, 4.123456, 8.75, 9.87654, 13.0, 25.0):
            p = price(bond, s, y)
            assert implied_yield(bond, s, p.aip) == round(y, 5)


@pytest.mark.parametrize("code", ["R2030", "R2048", "R188"])
def test_derivatives_match_finite_differences(code):
    bond = BONDS[code]
    s, y, h = date(2026, 11, 12), 8.9, 1e-4
    p, up, dn = price(bond, s, y), price(bond, s, y + h), price(bond, s, y - h)
    assert p.delta == pytest.approx((up.aip - dn.aip) / (2 * h), rel=1e-7)
    h = 1e-2  # a wider step for the second difference, which rounding noise swamps at 1e-4
    up, dn = price(bond, s, y + h), price(bond, s, y - h)
    assert p.d2aip_dy2 == pytest.approx((up.aip - 2 * p.aip + dn.aip) / h**2, rel=1e-4)
    assert p.dmod == pytest.approx(-100 * p.delta / p.aip, rel=1e-15)
