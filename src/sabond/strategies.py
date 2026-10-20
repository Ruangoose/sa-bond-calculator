"""Option strategies on a bond: several legs on the same bond, expiry and repo rate.

Each leg is an option valued by sabond.options.bond_option, bought or sold, in a given ratio. The
structure's premium and Greeks are the legs' sums, signed: a sold leg counts negative. Its payoff at
expiry is piecewise linear in the bond's all-in price for delivery (with a kink at each strike), so the
breakevens and the extremes are found exactly, then turned into yields with the JSE formula.

The built-in structures place each strike a set number of basis points of yield from the at-the-money
strike (the forward yield, rounded to a basis point). A call is a call on price, so a strike yield
below the forward is an out-of-the-money call.
"""

from dataclasses import dataclass
from datetime import date

from .bonds import Bond
from .calendar import add_business_days, settlement_date
from .jse import implied_yield, price
from .options import BondOption, bond_option
from .rounding import round_half_up


@dataclass(frozen=True)
class LegSpec:
    kind: str  # "call" or "put"
    side: int  # +1 buy, -1 sell
    ratio: float  # contracts per contract of the structure
    offset_bp: float  # strike yield, in basis points from the at-the-money strike


B, S = 1, -1
STRATEGIES: dict[str, tuple[LegSpec, ...]] = {
    "Call": (LegSpec("call", B, 1, 0),),
    "Put": (LegSpec("put", B, 1, 0),),
    "Call spread": (LegSpec("call", B, 1, 0), LegSpec("call", S, 1, -25)),
    "Put spread": (LegSpec("put", B, 1, 0), LegSpec("put", S, 1, 25)),
    "Risk reversal": (LegSpec("call", B, 1, -25), LegSpec("put", S, 1, 25)),
    "Straddle": (LegSpec("call", B, 1, 0), LegSpec("put", B, 1, 0)),
    "Strangle": (LegSpec("call", B, 1, -25), LegSpec("put", B, 1, 25)),
    "Fence": (LegSpec("call", S, 1, -50), LegSpec("call", B, 1, 0), LegSpec("put", S, 1, 50)),
    "Butterfly": (LegSpec("call", B, 1, -20), LegSpec("call", S, 1, 0), LegSpec("put", S, 1, 0),
                  LegSpec("put", B, 1, 20)),
}


@dataclass(frozen=True)
class Leg:
    kind: str
    side: int
    ratio: float
    strike_yield: float
    price_vol: float | None = None  # this leg's price volatility, if it differs from the structure's


def strategy_legs(name: str, atm_strike: float) -> list[Leg]:
    """A built-in structure's legs, with strikes placed around the at-the-money strike yield."""
    return [Leg(s.kind, s.side, s.ratio, round_half_up(atm_strike + s.offset_bp / 100, 2)) for s in STRATEGIES[name]]


@dataclass(frozen=True)
class LegValue:
    kind: str
    side: int
    ratio: float
    strike_yield: float
    option: BondOption
    weight: float  # side x ratio
    premium: float  # rand per structure, signed: positive is paid
    delta: float
    gamma: float
    vega: float
    theta: float


@dataclass(frozen=True)
class Strategy:
    bond: str
    trade_date: date
    expiry: date
    delivery: date
    notional: float
    legs: tuple[LegValue, ...]
    net_premium: float  # rand per structure: positive, you pay; negative, you receive
    delta: float  # net, per unit of forward price
    gamma: float
    vega: float  # rand per volatility point
    theta: float  # rand per day
    yield_delta: float  # rand for a 1bp rise in the spot yield
    delta_nominal: float  # rand of bond nominal the net delta is worth
    breakevens: tuple[float, ...]  # yields at expiry, ascending
    max_profit: float | None  # rand per structure at expiry; None if uncapped
    max_loss: float | None  # rand per structure at expiry (negative); None if uncapped
    max_profit_yield: float | None
    max_loss_yield: float | None


def payoff_at_price(legs, price_at_delivery: float, notional: float) -> float:
    """Profit or loss at expiry, rand per structure, at a given all-in price for delivery."""
    total = 0.0
    for leg in legs:
        k = leg.option.strike_aip
        gain = price_at_delivery - k if leg.kind == "call" else k - price_at_delivery
        total += leg.weight * (max(gain, 0.0) * notional / 100 - leg.option.premium)
    return total


def payoff(strategy: "Strategy", bond: Bond, expiry_yield: float) -> float:
    """Profit or loss at expiry, rand per structure, if the bond's yield at expiry is `expiry_yield`."""
    p = price(bond, strategy.delivery, expiry_yield).aip_r
    return payoff_at_price(strategy.legs, p, strategy.notional)


def value_strategy(
    bond: Bond,
    trade_date: date,
    expiry: date,
    spot_yield: float,
    carry_rate: float,
    price_vol: float,
    legs: list[Leg],
    notional: float = 100_000,
    spot_settle: date | None = None,
    window: tuple[float, float] | None = None,
    extra_holidays=(),
) -> Strategy:
    """Value a structure. Yields and the carry rate are in %; price_vol is a decimal, for every leg that
    doesn't set its own.

    `window` is the range of yields at expiry over which a capped maximum profit or loss is looked for;
    by default the strikes plus and minus three percentage points.
    """
    spot_settle = spot_settle or settlement_date(trade_date, extra_holidays)
    delivery = add_business_days(expiry, 3, extra_holidays)
    values = []
    for leg in legs:
        vol = price_vol if leg.price_vol is None else leg.price_vol
        o = bond_option(bond, trade_date, expiry, spot_yield, leg.strike_yield, carry_rate, vol, leg.kind,
                        notional=notional, spot_settle=spot_settle, delivery=delivery, extra_holidays=extra_holidays)
        w = leg.side * leg.ratio
        values.append(LegValue(leg.kind, leg.side, leg.ratio, leg.strike_yield, o, w, w * o.premium,
                               w * o.delta, w * o.gamma, w * o.vega, w * o.theta))
    values = tuple(values)
    total = lambda f: sum(f(v) for v in values)  # noqa: E731

    # The payoff is linear in the price between strikes. The vertices: the window's edges and each strike.
    strikes_y = [leg.strike_yield for leg in legs]
    lo_y, hi_y = window or (min(strikes_y) - 3, max(strikes_y) + 3)
    p_hi = price(bond, delivery, lo_y).aip_r  # low yield, high price
    p_lo = price(bond, delivery, hi_y).aip_r
    vertices = sorted({p_lo, p_hi, *(v.option.strike_aip for v in values if p_lo < v.option.strike_aip < p_hi)})
    pay = [payoff_at_price(values, p, notional) for p in vertices]
    # Slopes beyond every strike: above, only calls pay; below, only puts.
    slope_high = sum(v.weight * notional / 100 for v in values if v.kind == "call")
    slope_low = -sum(v.weight * notional / 100 for v in values if v.kind == "put")
    eps = 1e-9
    profit_uncapped = slope_low < -eps or slope_high > eps
    loss_uncapped = slope_low > eps or slope_high < -eps

    def yield_at(p):
        return implied_yield(bond, delivery, p)

    breakevens = set()
    for i, (p, v) in enumerate(zip(vertices, pay)):
        if v == 0:
            breakevens.add(yield_at(p))
        if i + 1 < len(vertices) and v * pay[i + 1] < 0:
            t = -v / (pay[i + 1] - v)
            breakevens.add(yield_at(p + t * (vertices[i + 1] - p)))
    # Where the payoff is flat (a capped spread, say), several vertices tie, to within floating-point
    # noise. Of those, take the one nearest the strikes: the edge of the flat stretch.
    middle = sum(v.option.strike_aip for v in values) / len(values)

    def pick(target):
        ties = [i for i in range(len(pay)) if abs(pay[i] - target) <= 1e-6]
        return min(ties, key=lambda i: (abs(vertices[i] - middle), i))

    best = pick(max(pay))
    worst = pick(min(pay))
    return Strategy(
        bond=bond.code,
        trade_date=trade_date,
        expiry=expiry,
        delivery=delivery,
        notional=notional,
        legs=values,
        net_premium=total(lambda v: v.premium),
        delta=total(lambda v: v.delta),
        gamma=total(lambda v: v.gamma),
        vega=total(lambda v: v.vega),
        theta=total(lambda v: v.theta),
        yield_delta=total(lambda v: v.weight * v.option.yield_delta),
        delta_nominal=total(lambda v: v.delta) * notional,
        breakevens=tuple(sorted(breakevens)),
        max_profit=None if profit_uncapped else pay[best],
        max_loss=None if loss_uncapped else pay[worst],
        max_profit_yield=None if profit_uncapped else yield_at(vertices[best]),
        max_loss_yield=None if loss_uncapped else yield_at(vertices[worst]),
    )
