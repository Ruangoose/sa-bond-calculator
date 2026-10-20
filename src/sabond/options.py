"""Options on South African government bonds: Black (1976) on the forward all-in price.

The method, as South African desks use it for over-the-counter bond options:
- The underlying is the bond's forward all-in price for delivery three business days after expiry,
  from cost of carry (see carry.py).
- The strike is quoted as a yield and converted to an all-in price for that delivery date with the
  JSE formula.
- Volatility is a price volatility. The yield volatility it implies is shown alongside, using the
  forward modified duration: yield vol = price vol / (duration x forward yield).
- Time is calendar days from trade date to expiry, over 365.
- The premium is Black's forward value with no discounting, per R100 nominal; per contract it scales
  by the contract's nominal (R100,000 by default, the JSE's contract size).
- Calls and puts are on price: a call gains when yields fall.
"""

from dataclasses import dataclass
from datetime import date
from math import log, sqrt

from .bonds import Bond
from .calendar import add_business_days, settlement_date
from .carry import Forward, forward
from .jse import price
from .normal import norm_cdf, norm_pdf


@dataclass(frozen=True)
class Black:
    value: float
    delta: float  # dV/dF
    gamma: float  # d2V/dF2
    vega: float  # dV/dsigma, per unit of volatility
    theta: float  # dV/dt per year, as time passes (negative)
    d1: float
    d2: float


def black76(fwd: float, strike: float, t: float, vol: float, kind: str = "call") -> Black:
    """Black's (1976) model for an option on a forward price, undiscounted."""
    if kind not in ("call", "put"):
        raise ValueError("kind must be 'call' or 'put'")
    if t <= 0 or vol <= 0:
        raise ValueError("time to expiry and volatility must be positive")
    s = vol * sqrt(t)
    d1 = (log(fwd / strike) + s * s / 2) / s
    d2 = d1 - s
    if kind == "call":
        value = fwd * norm_cdf(d1) - strike * norm_cdf(d2)
        delta = norm_cdf(d1)
    else:
        value = strike * norm_cdf(-d2) - fwd * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1
    pdf = norm_pdf(d1)
    return Black(
        value=value,
        delta=delta,
        gamma=pdf / (fwd * s),
        vega=fwd * sqrt(t) * pdf,
        theta=-fwd * pdf * vol / (2 * sqrt(t)),
        d1=d1,
        d2=d2,
    )


@dataclass(frozen=True)
class BondOption:
    bond: str
    kind: str
    trade_date: date
    expiry: date
    t: float  # years, calendar days / 365
    forward: Forward
    strike_yield: float
    strike_aip: float  # rounded all-in price at the strike yield, for delivery
    price_vol: float  # decimal, e.g. 0.12 for 12%
    yield_vol: float  # the equivalent yield volatility, decimal
    forward_dmod: float  # modified duration at the forward yield, for delivery
    notional: float  # rand per contract
    value: float  # per R100 nominal
    premium: float  # rand per contract
    delta: float  # per unit of forward price (the sheet's "delta per contract")
    delta_nominal: float  # rand of bond nominal per contract that the delta is worth
    gamma: float
    vega: float  # rand per contract per 1 volatility point
    theta: float  # rand per contract per calendar day
    yield_delta: float  # rand per contract for a 1bp rise in the spot yield


def bond_option(
    bond: Bond,
    trade_date: date,
    expiry: date,
    spot_yield: float,
    strike_yield: float,
    carry_rate: float,
    price_vol: float,
    kind: str = "call",
    notional: float = 100_000,
    spot_settle: date | None = None,
    delivery: date | None = None,
    extra_holidays=(),
) -> BondOption:
    """Value an option on a bond. Yields and the carry rate are in %, price_vol is a decimal."""
    if expiry <= trade_date:
        raise ValueError("expiry must be after the trade date")
    spot_settle = spot_settle or settlement_date(trade_date, extra_holidays)
    delivery = delivery or add_business_days(expiry, 3, extra_holidays)
    fwd = forward(bond, spot_settle, delivery, spot_yield, carry_rate)
    strike_aip = price(bond, delivery, strike_yield).aip_r
    t = (expiry - trade_date).days / 365
    b = black76(fwd.aip, strike_aip, t, price_vol, kind)
    fwd_dmod = price(bond, delivery, fwd.ytm).dmod
    scale = notional / 100
    # The forward moves with the spot price, carried: dF/dy = dAIP/dy x (1 + r x days / 365).
    spot_delta = price(bond, spot_settle, spot_yield).delta  # per 1% of yield
    dfwd_dy = spot_delta * (1 + carry_rate / 100 * fwd.days / 365)
    return BondOption(
        bond=bond.code,
        kind=kind,
        trade_date=trade_date,
        expiry=expiry,
        t=t,
        forward=fwd,
        strike_yield=strike_yield,
        strike_aip=strike_aip,
        price_vol=price_vol,
        yield_vol=price_vol / (fwd_dmod * fwd.ytm / 100),
        forward_dmod=fwd_dmod,
        notional=notional,
        value=b.value,
        premium=b.value * scale,
        delta=b.delta,
        delta_nominal=b.delta * notional,
        gamma=b.gamma,
        vega=b.vega * scale / 100,
        theta=b.theta / 365 * scale,
        yield_delta=b.delta * dfwd_dy * scale / 100,
    )


def price_vol_from_yield_vol(yield_vol: float, forward_dmod: float, forward_ytm: float) -> float:
    """The price volatility equivalent to a yield volatility (both decimals; yield in %)."""
    return yield_vol * forward_dmod * forward_ytm / 100
