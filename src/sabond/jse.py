"""The JSE Bond Pricing Formula for South African fixed-coupon bonds.

This follows the JSE's "Bond Pricing Formula - Specifications" (Bond Exchange of South Africa,
version 2, 24 August 2005), section by section. Section numbers in the comments are the document's.
Yields and coupons are percentages (7.5 means 7.5%), prices are per R100 nominal, and every date is
a settlement date.
"""

from dataclasses import dataclass, field
from datetime import date

from .bonds import Bond
from .rounding import round_half_up

PROUND = 5  # price rounding, decimal places (footnote 10)
YROUND = 5  # implied-yield rounding, decimal places (7.2)


def _on(year: int, day_month: tuple[int, int]) -> date:
    """A coupon or books-closed date in a given year. 29 February codes 'last day of February'."""
    day, month = day_month
    if month == 2 and day == 29 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        day = 28
    return date(year, month, day)


@dataclass(frozen=True)
class Timing:
    """Section 3: where the settlement date sits against the bond's coupon and books-closed dates."""

    settle: date
    lcd: date  # 3.1 last coupon date, on or before settlement
    ncd: date  # 3.2 next coupon date, after settlement
    bcd: date  # 3.3 books-closed date for NCD
    n: int  # 3.4 coupon dates after NCD, up to and including maturity
    cumex: int  # 3.5 1 if cum interest, 0 if ex
    days_acc: int  # 3.6 days of accrued interest (negative when ex)
    last_period: bool  # NCD is the maturity date: priced as a money-market instrument


def timing(bond: Bond, settle: date) -> Timing:
    if settle >= bond.maturity:
        raise ValueError(f"{bond.code} matures on {bond.maturity}; settlement {settle} is not before it")
    dates = sorted(_on(y, dm) for y in range(settle.year - 1, settle.year + 2) for dm in bond.coupon_dates)
    lcd = max(d for d in dates if d <= settle)
    ncd = min(d for d in dates if d > settle)
    i = [m for _, m in bond.coupon_dates].index(ncd.month)
    bcd = _on(ncd.year, bond.books_closed[i])
    if bcd > ncd:
        bcd = _on(ncd.year - 1, bond.books_closed[i])
    if not lcd < bcd <= ncd:
        raise ValueError(f"{bond.code}: books-closed date {bcd} is not between {lcd} and {ncd}")
    # Footnote 14: N = ROUND[(MB - NCD) / (365.25/2), 0].
    n = int(round_half_up((bond.maturity - ncd).days / (365.25 / 2), 0))
    cumex = 1 if settle < bcd else 0
    days_acc = (settle - lcd).days if cumex else (settle - ncd).days
    return Timing(settle, lcd, ncd, bcd, n, cumex, days_acc, ncd == bond.maturity)


@dataclass(frozen=True)
class Price:
    """Every result in sections 3 to 6, for one bond, settlement date and yield.

    Names follow the specification. Fields ending in _r are rounded by the JSE's conventions; the
    others are held to full precision.
    """

    bond: str
    settle: date
    ytm: float
    lcd: date
    ncd: date
    bcd: date
    n: int
    cumex: int
    days_acc: int
    cpn: float  # 3.7 basic coupon
    cpn_ncd: float  # 3.8 coupon payable on NCD
    f: float  # 3.9 semi-annual discount factor
    bp: float  # 3.10 broken period
    bpf: float  # 3.11 broken-period discount factor
    dbpf: float  # 3.12
    d2bpf: float  # 3.13
    accrint: float  # 4.1
    accrint_r: float  # 4.2
    aip: float  # 4.3 all-in price
    cp: float  # 4.4 clean price
    cp_r: float  # 4.5
    aip_r: float  # 4.6
    dcpn: float  # 4.7
    d2cpn: float
    dr: float
    d2r: float
    daip: float  # 4.8 dAIP/dF
    d2aip: float  # 4.9 d2AIP/dF2
    delta: float  # 6.1 dAIP/dY, rand per R100 nominal per 1% of yield
    rands_per_point: float  # 6.1 per R1m nominal per 0.01%, sign dropped
    dmod: float  # 6.2 modified duration, years
    dur: float  # 6.3 duration, years
    d2aip_dy2: float  # 6.4 second differential, rand per R100 per (1%)^2
    conv: float  # 6.4 convexity
    nominal: float | None = None
    int_consid: float | None = None  # 5.1
    allin_consid: float | None = None  # 5.2
    clean_consid: float | None = None  # 5.3


@dataclass(frozen=True)
class _Values:
    f: float
    bp: float
    bpf: float
    dbpf: float
    d2bpf: float
    aip: float
    dcpn: float
    d2cpn: float
    dr: float
    d2r: float
    daip: float
    d2aip: float


def _values(bond: Bond, t: Timing, ytm: float) -> _Values:
    """Sections 3.9 to 4.9 for a given yield: the all-in price and its derivatives in F."""
    cpn = bond.coupon / 2
    cpn_ncd = cpn * t.cumex
    r = bond.redemption
    n = t.n
    f = 1 / (1 + ytm / 200)  # 3.9
    if not t.last_period:  # 3.10 to 3.13
        bp = (t.ncd - t.settle).days / (t.ncd - t.lcd).days
        bpf = f**bp
        dbpf = bp * bpf / f
        d2bpf = dbpf * (bp - 1) / f
    else:
        bp = (t.ncd - t.settle).days / (365 / 2)
        bpf = f / (f + bp * (1 - f))
        dbpf = bp * bpf**2 / f**2
        d2bpf = 2 * dbpf * (bp * bpf - f) / f**2
    fn = f**n
    if f != 1:  # Equations 3, 7 and 8
        annuity = cpn * f * (1 - fn) / (1 - f)
        dcpn = cpn * (1 - (n - n * f + 1) * fn) / (1 - f) ** 2
        d2cpn = cpn * (2 - (n * (1 - f) * (2 + (n - 1) * (1 - f)) + 2 * f) * f ** (n - 1)) / (1 - f) ** 3
    else:
        annuity = cpn * n
        dcpn = cpn * n * (n + 1) / 2
        d2cpn = cpn * n * (n * n - 1) / 3
    dr = n * r * f ** (n - 1)  # Equation 9
    d2r = n * (n - 1) * r * f ** (n - 2)  # Equation 10
    body = cpn_ncd + annuity + r * fn  # AIP / BPF
    aip = bpf * body
    daip = dbpf * body + bpf * (dcpn + dr)  # Equation 11
    d2aip = d2bpf * body + 2 * dbpf * (dcpn + dr) + bpf * (d2cpn + d2r)  # Equation 12
    return _Values(f, bp, bpf, dbpf, d2bpf, aip, dcpn, d2cpn, dr, d2r, daip, d2aip)


def price(bond: Bond, settle: date, ytm: float, nominal: float | None = None) -> Price:
    """Price a bond at a yield (in %) for a settlement date, per R100 nominal.

    With `nominal` (in rand), the three considerations of section 5 are filled in too.
    """
    t = timing(bond, settle)
    v = _values(bond, t, ytm)
    accrint = t.days_acc * bond.coupon / 365  # 4.1, actual/365
    accrint_r = round_half_up(accrint, PROUND)  # 4.2
    cp = v.aip - accrint  # 4.4
    cp_r = round_half_up(cp, PROUND)  # 4.5
    aip_r = round_half_up(cp_r + accrint_r, PROUND)  # 4.6 (re-rounded only to clear float noise)
    delta = -(v.f**2) / 200 * v.daip  # 6.1
    dmod = -100 * delta / v.aip  # 6.2
    d2aip_dy2 = (v.d2aip * v.f**4 + 2 * v.daip * v.f**3) / 40000  # 6.4
    consid = {}
    if nominal is not None:
        int_consid = round_half_up(accrint_r * nominal / 100, 2)  # 5.1
        allin_consid = round_half_up(aip_r * nominal / 100, 2)  # 5.2
        consid = dict(
            nominal=nominal,
            int_consid=int_consid,
            allin_consid=allin_consid,
            clean_consid=round_half_up(allin_consid - int_consid, 2),  # 5.3
        )
    return Price(
        bond=bond.code,
        settle=settle,
        ytm=ytm,
        lcd=t.lcd,
        ncd=t.ncd,
        bcd=t.bcd,
        n=t.n,
        cumex=t.cumex,
        days_acc=t.days_acc,
        cpn=bond.coupon / 2,
        cpn_ncd=bond.coupon / 2 * t.cumex,
        f=v.f,
        bp=v.bp,
        bpf=v.bpf,
        dbpf=v.dbpf,
        d2bpf=v.d2bpf,
        accrint=accrint,
        accrint_r=accrint_r,
        aip=v.aip,
        cp=cp,
        cp_r=cp_r,
        aip_r=aip_r,
        dcpn=v.dcpn,
        d2cpn=v.d2cpn,
        dr=v.dr,
        d2r=v.d2r,
        daip=v.daip,
        d2aip=v.d2aip,
        delta=delta,
        rands_per_point=-100 * delta,
        dmod=dmod,
        dur=dmod / v.f,  # 6.3
        d2aip_dy2=d2aip_dy2,
        conv=10000 / v.aip * d2aip_dy2,  # 6.4
        **consid,
    )


def accrued_interest(bond: Bond, settle: date) -> float:
    """Rounded accrued interest per R100 nominal (4.2). It doesn't depend on the yield."""
    t = timing(bond, settle)
    return round_half_up(t.days_acc * bond.coupon / 365, PROUND)


@dataclass(frozen=True)
class Step:
    """One column of the section 7.2 iteration."""

    y: float
    f: float
    aip: float
    daip: float
    d2aip: float
    diff: float
    next_f: float
    next_y: float
    prev: float
    opp: float


@dataclass(frozen=True)
class ImpliedYield:
    yield_: float
    steps: list[Step] = field(default_factory=list)


class NoConvergence(ValueError):
    pass


def implied_yield(
    bond: Bond,
    settle: date,
    aip: float,
    *,
    y0: float = 10.0,
    itn_lim: int = 20,
    min_y: float = -67.0,
    max_y: float = 200.0,
    trace: bool = False,
):
    """The yield, rounded to 5 decimal places, whose unrounded all-in price equals `aip` (section 7).

    This is the document's recommended algorithm: Bailey's method with its convergence test. The
    document suggests an iteration limit of 5 and allows more; 20 leaves room for unusual inputs.
    Returns the yield, or with trace=True an ImpliedYield holding every step.
    """
    t = timing(bond, settle)
    y = y0
    steps = []
    for _ in range(itn_lim + 1):
        v = _values(bond, t, y)
        diff = v.aip - aip
        next_f = v.f - diff / (v.daip - diff * v.d2aip / (2 * v.daip))
        next_y = 200 / next_f - 200
        if not min_y <= next_y <= max_y:
            break
        prev = round_half_up(y, YROUND)
        opp = round_half_up(2 * next_y - y, YROUND)
        steps.append(Step(y, v.f, v.aip, v.daip, v.d2aip, diff, next_f, next_y, prev, opp))
        if prev == opp:
            return ImpliedYield(opp, steps) if trace else opp
        y = next_y
    raise NoConvergence(f"{bond.code}: no yield found for all-in price {aip} on {settle}")
