from datetime import date, timedelta

import pytest

from sabond import BONDS, forward, price


def test_no_coupon_in_the_carry_period():
    bond = BONDS["R2030"]  # coupons 31 Jan and 31 Jul
    s0, s1 = date(2026, 10, 23), date(2026, 11, 10)
    f = forward(bond, s0, s1, 8.2, 7.4)
    assert f.coupons == ()
    assert f.aip == pytest.approx(price(bond, s0, 8.2).aip_r * (1 + 0.074 * 18 / 365), rel=1e-15)
    assert price(bond, s1, f.ytm).aip == pytest.approx(f.aip, abs=2e-4)


def test_coupon_paid_in_the_carry_period_is_carried_to_delivery():
    bond = BONDS["R2032"]  # coupons 31 Mar and 30 Sep, books close 21 Mar and 20 Sep
    s0, s1 = date(2026, 12, 15), date(2027, 5, 11)
    f = forward(bond, s0, s1, 8.6, 7.4)
    (c,) = f.coupons
    assert c.paid == date(2027, 3, 31) and c.books_closed == date(2027, 3, 21)
    assert c.value_at_delivery == pytest.approx(4.125 * (1 + 0.074 * 41 / 365), rel=1e-15)
    assert f.aip == pytest.approx(f.carried_aip - c.value_at_delivery, rel=1e-15)


def test_spot_already_ex_keeps_no_coupon():
    # Settling inside the books-closed period: the spot price already excludes the coupon.
    bond = BONDS["R2032"]
    s1 = date(2027, 5, 11)
    cum = forward(bond, date(2027, 3, 20), s1, 8.6, 7.4)
    ex = forward(bond, date(2027, 3, 21), s1, 8.6, 7.4)
    assert len(cum.coupons) == 1 and ex.coupons == ()
    assert abs(cum.aip - ex.aip) < 0.05  # no coupon-sized jump
    assert abs(cum.ytm - ex.ytm) < 0.01


def test_delivery_inside_books_closed_discounts_the_coupon():
    # Books close by delivery but the coupon is paid after it: the carry-period holder is on the
    # register, so the coupon is theirs, worth its discounted value at delivery.
    bond = BONDS["R2032"]
    s0 = date(2027, 2, 1)
    before = forward(bond, s0, date(2027, 3, 19), 8.6, 7.4)
    inside = forward(bond, s0, date(2027, 3, 23), 8.6, 7.4)
    assert before.coupons == ()
    (c,) = inside.coupons
    assert c.paid == date(2027, 3, 31)
    assert c.value_at_delivery == pytest.approx(4.125 / (1 + 0.074 * 8 / 365), rel=1e-15)
    assert abs(inside.ytm - before.ytm) < 0.02  # the forward yield doesn't jump


def test_forward_yield_moves_with_carry():
    bond = BONDS["R2035"]
    s0, s1 = date(2026, 10, 23), date(2027, 2, 9)
    low = forward(bond, s0, s1, 9.0, 5.0)
    high = forward(bond, s0, s1, 9.0, 12.0)
    # Funding below the bond's yield earns carry, so the forward yield sits above spot.
    assert low.ytm > 9.0 > high.ytm


def test_delivery_must_be_before_maturity():
    with pytest.raises(ValueError):
        forward(BONDS["R187"], date(2026, 10, 23), date(2026, 12, 22), 7.0, 7.0)
    with pytest.raises(ValueError):
        forward(BONDS["R2030"], date(2026, 10, 23), date(2026, 10, 23) - timedelta(days=1), 8.0, 7.0)
