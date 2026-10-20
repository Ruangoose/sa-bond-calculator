"""Bond forwards and futures by cost of carry.

A forward on a bond, for delivery on a later settlement date, is worth the spot all-in price carried
to that date at the funding (repo) rate, less the coupons the holder collects on the way, carried to
the same date. Interest is simple, actual/365, as in the South African money market. The forward
all-in price converts back to a yield with the JSE formula for the delivery date.

A JSE bond future is this forward: it expires on the first business Thursday of February, May,
August and November, it is quoted as a yield for settlement on the delivery date (expiry plus three
business days), and that yield converts to the delivery price with the JSE formula (JSE, "Futures on
Nominal Bonds", product specification, December 2016).

Coupons: a coupon belongs to whoever holds the bond on its books-closed date. The holder over the
carry period collects every coupon whose books-closed date falls after spot settlement and on or
before delivery. One paid by delivery is carried forward to it; one whose books close by delivery but
which is paid after it is discounted back to it.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from .bonds import Bond
from .calendar import add_business_days, is_business_day
from .jse import _on, implied_yield, price


@dataclass(frozen=True)
class Coupon:
    paid: date
    books_closed: date
    amount: float  # per R100 nominal
    value_at_delivery: float


@dataclass(frozen=True)
class Forward:
    bond: str
    spot_settle: date
    delivery: date
    spot_yield: float
    carry_rate: float  # % a year, simple, actual/365
    spot_aip: float  # rounded all-in price for spot settlement
    days: int
    carried_aip: float  # spot all-in price carried to delivery
    coupons: tuple[Coupon, ...]
    coupon_value: float  # the coupons, valued at delivery
    aip: float  # forward all-in price for delivery
    ytm: float  # forward yield, rounded to 5 decimal places


def coupons_between(bond: Bond, after: date, through: date):
    """(payment date, books-closed date) for each coupon whose books close in (after, through]."""
    out = []
    for year in range(after.year, through.year + 2):
        for dm, bc in zip(bond.coupon_dates, bond.books_closed):
            paid = _on(year, dm)
            if paid > bond.maturity:
                continue
            closed = _on(year, bc)
            if closed > paid:
                closed = _on(year - 1, bc)
            if after < closed <= through:
                out.append((paid, closed))
    return sorted(out)


def forward(
    bond: Bond,
    spot_settle: date,
    delivery: date,
    spot_yield: float,
    carry_rate: float,
) -> Forward:
    """The forward all-in price and yield of a bond for a delivery date, from its spot yield."""
    if delivery <= spot_settle:
        raise ValueError("delivery must be after spot settlement")
    if delivery >= bond.maturity:
        raise ValueError(f"{bond.code} matures on {bond.maturity}, before delivery on {delivery}")
    r = carry_rate / 100
    spot_aip = price(bond, spot_settle, spot_yield).aip_r
    days = (delivery - spot_settle).days
    carried = spot_aip * (1 + r * days / 365)
    coupons = []
    for paid, closed in coupons_between(bond, spot_settle, delivery):
        amount = bond.coupon / 2
        if paid <= delivery:
            value = amount * (1 + r * (delivery - paid).days / 365)
        else:
            value = amount / (1 + r * (paid - delivery).days / 365)
        coupons.append(Coupon(paid, closed, amount, value))
    coupon_value = sum(c.value_at_delivery for c in coupons)
    aip = carried - coupon_value
    return Forward(
        bond=bond.code,
        spot_settle=spot_settle,
        delivery=delivery,
        spot_yield=spot_yield,
        carry_rate=carry_rate,
        spot_aip=spot_aip,
        days=days,
        carried_aip=carried,
        coupons=tuple(coupons),
        coupon_value=coupon_value,
        aip=aip,
        ytm=implied_yield(bond, delivery, aip),
    )


def futures_expiry(year: int, month: int, extra_holidays=()) -> date:
    """The first business Thursday of a month: the JSE's bond futures expiry day."""
    d = date(year, month, 1)
    d += timedelta(days=(3 - d.weekday()) % 7)
    while not is_business_day(d, extra_holidays):
        d += timedelta(days=7)
    return d


def futures_expiries(after: date, count: int = 4, extra_holidays=()) -> list[date]:
    """The next `count` JSE bond futures expiry dates after a date (February, May, August, November)."""
    out = []
    year = after.year
    while len(out) < count:
        for month in (2, 5, 8, 11):
            d = futures_expiry(year, month, extra_holidays)
            if d > after and len(out) < count:
                out.append(d)
        year += 1
    return out


def futures_delivery(expiry: date, extra_holidays=()) -> date:
    """Delivery of the bond: three business days after expiry."""
    return add_business_days(expiry, 3, extra_holidays)
