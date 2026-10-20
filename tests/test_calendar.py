from datetime import date

from sabond import add_business_days, public_holidays, settlement_date
from sabond.calendar import easter_sunday
from sabond.carry import futures_delivery, futures_expiries, futures_expiry


def test_easter():
    assert easter_sunday(2024) == date(2024, 3, 31)
    assert easter_sunday(2025) == date(2025, 4, 20)
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)


def test_holidays_2026():
    h = public_holidays(2026)
    assert date(2026, 4, 3) in h and date(2026, 4, 6) in h  # Good Friday, Family Day
    assert date(2026, 8, 10) in h  # Women's Day falls on a Sunday, so Monday is the holiday
    assert len(h) == 13


def test_t_plus_3():
    assert settlement_date(date(2026, 7, 29)) == date(2026, 8, 3)  # over a weekend
    assert settlement_date(date(2026, 8, 6)) == date(2026, 8, 12)  # over a weekend and a holiday
    assert add_business_days(date(2026, 8, 12), -3) == date(2026, 8, 6)


def test_futures_dates():
    # The JSE spec's own example code is "03 August 17 R186".
    assert futures_expiry(2017, 8) == date(2017, 8, 3)
    assert futures_expiries(date(2026, 10, 20)) == [
        date(2026, 11, 5),
        date(2027, 2, 4),
        date(2027, 5, 6),
        date(2027, 8, 5),
    ]
    assert futures_delivery(date(2026, 11, 5)) == date(2026, 11, 10)
    # The JSE moved delivery for the 6 August 2020 expiry to 12 August, as 10 August was a holiday.
    assert futures_delivery(date(2020, 8, 6)) == date(2020, 8, 12)
