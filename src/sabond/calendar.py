"""South African business days, for settlement dates.

Public holidays follow the Public Holidays Act 36 of 1994: the twelve holidays in its Schedule, with
a holiday that falls on a Sunday moving to the Monday after it (section 2(1)). One-off holidays the
President declares under section 2A (election days, for example) are not built in; pass them as
`extra_holidays` where they matter.
"""

from datetime import date, timedelta
from functools import lru_cache


def easter_sunday(year: int) -> date:
    """Western Easter Sunday (the anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=None)
def public_holidays(year: int) -> frozenset[date]:
    """The statutory public holidays in a year, with Sunday holidays moved to Monday."""
    easter = easter_sunday(year)
    fixed = [
        date(year, 1, 1),  # New Year's Day
        date(year, 3, 21),  # Human Rights Day
        date(year, 4, 27),  # Freedom Day
        date(year, 5, 1),  # Workers' Day
        date(year, 6, 16),  # Youth Day
        date(year, 8, 9),  # National Women's Day
        date(year, 9, 24),  # Heritage Day
        date(year, 12, 16),  # Day of Reconciliation
        date(year, 12, 25),  # Christmas Day
        date(year, 12, 26),  # Day of Goodwill
    ]
    days = set(fixed)
    days.add(easter - timedelta(days=2))  # Good Friday
    days.add(easter + timedelta(days=1))  # Family Day
    for d in fixed:
        if d.weekday() == 6:
            days.add(d + timedelta(days=1))
    return frozenset(days)


def is_business_day(d: date, extra_holidays=()) -> bool:
    return d.weekday() < 5 and d not in public_holidays(d.year) and d not in extra_holidays


def add_business_days(d: date, n: int, extra_holidays=()) -> date:
    """The date n business days after d (before it, if n is negative)."""
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining:
        d += timedelta(days=step)
        if is_business_day(d, extra_holidays):
            remaining -= 1
    return d


def settlement_date(trade_date: date, extra_holidays=()) -> date:
    """Bond settlement for a trade: T+3 business days, the JSE's convention."""
    return add_business_days(trade_date, 3, extra_holidays)
