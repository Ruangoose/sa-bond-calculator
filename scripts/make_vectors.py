"""Write the JavaScript port's bond table, test vectors and worked example from the Python package.

    python scripts/make_vectors.py          # write web/bonds.js, web/vectors.json, web/example.json
    python scripts/make_vectors.py --check  # fail if any of them is out of date

The Python package is the source of truth.
- web/bonds.js is the bond table in JavaScript.
- web/vectors.json holds inputs and the Python's outputs for prices, implied yields, settlement and
  futures dates, forwards and options. Inputs are spread deterministically across every bond, edge
  dates (coupon and books-closed dates, the last coupon period, leap days) and a wide range of yields.
- web/example.json is the worked example on the website's project page: one bond, future and option,
  with the points of its two charts. The page shows it as is when JavaScript is off.
web/sabond.test.mjs checks the port against every vector and the example. All yields are illustrative.
"""

import json
import random
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sabond import (  # noqa: E402
    BONDS,
    bond_option,
    forward,
    futures_delivery,
    futures_expiries,
    futures_expiry,
    implied_yield,
    price,
    settlement_date,
)
from sabond.jse import _on  # noqa: E402
from sabond.rounding import round_half_up  # noqa: E402

START = date(2026, 10, 1)
YIELDS = [0.0, 0.75, 3.5, 5.125, 6.4, 7.0, 7.333333, 7.85, 8.25, 8.6, 9.0, 9.123456789, 9.5, 9.875, 10.2, 10.75,
          11.5, 12.25, 13.0, 15.0, 18.5, 25.0]


def iso(d):
    return d.isoformat()


def edge_dates(bond, years=3):
    """Dates around each coupon and books-closed date in the next few years."""
    out = set()
    for y in range(START.year, START.year + years + 1):
        for dm, bc in zip(bond.coupon_dates, bond.books_closed):
            paid = _on(y, dm)
            closed = _on(y, bc) if _on(y, bc) < paid else _on(y - 1, bc)
            for d in (paid - timedelta(1), paid, paid + timedelta(1), closed - timedelta(1), closed):
                out.add(d)
    out |= {date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1)}
    return sorted(d for d in out if START <= d < bond.maturity)


def price_vectors(rng):
    rows = []
    for bond in BONDS.values():
        dates = set(edge_dates(bond))
        d = START
        while d < bond.maturity and d < START + timedelta(days=365 * 10):
            dates.add(d)
            d += timedelta(days=61)
        last = max(bond.maturity - timedelta(days=183), START)  # the final coupon period
        d = last
        while d < bond.maturity:
            dates.add(d)
            d += timedelta(days=17)
        for s in sorted(dates):
            for y in rng.sample(YIELDS, 2):
                p = price(bond, s, y, nominal=rng.choice([1_000_000, 1_500_000, 2_345_678.9, 100_000]))
                rows.append({k: (iso(v) if isinstance(v, date) else v) for k, v in asdict(p).items()})
    return rows


def yield_vectors(rng, prices):
    rows = []
    for p in rng.sample(prices, 600):
        bond, s = BONDS[p["bond"]], date.fromisoformat(p["settle"])
        for target in (p["aip_r"], p["aip"] + rng.uniform(-0.5, 0.5)):
            rows.append({"bond": p["bond"], "settle": p["settle"], "aip": target,
                         "ytm": implied_yield(bond, s, target)})
    return rows


def calendar_vectors():
    days = []
    d = date(2026, 1, 1)
    while d <= date(2029, 12, 31):
        days.append([iso(d), iso(settlement_date(d))])
        d += timedelta(days=1)
    expiries = []
    for year in range(2017, 2033):
        for month in (2, 5, 8, 11):
            e = futures_expiry(year, month)
            expiries.append([year, month, iso(e), iso(futures_delivery(e))])
    return {"settlement": days, "futures": expiries,
            "next_expiries": [[iso(a), [iso(e) for e in futures_expiries(a)]]
                              for a in (date(2026, 10, 20), date(2026, 11, 5), date(2027, 12, 31))]}


def forward_vectors(rng):
    rows = []
    for bond in BONDS.values():
        for _ in range(10):
            trade = START + timedelta(days=rng.randrange(0, 900))
            s0 = settlement_date(trade)
            deliveries = [futures_delivery(e) for e in futures_expiries(trade, 3)]
            deliveries.append(s0 + timedelta(days=rng.randrange(5, 400)))
            for s1 in deliveries:
                if s1 >= bond.maturity or s0 >= bond.maturity:
                    continue
                f = forward(bond, s0, s1, rng.choice(YIELDS[2:-2]), rng.choice([4.5, 6.75, 7.25, 8.0, 9.9]))
                row = asdict(f)
                row["coupons"] = [{k: (iso(v) if isinstance(v, date) else v) for k, v in c.items()}
                                  for c in row["coupons"]]
                rows.append({k: (iso(v) if isinstance(v, date) else v) for k, v in row.items()})
    return rows


def option_vectors(rng):
    rows = []
    for bond in BONDS.values():
        for _ in range(3):
            trade = START + timedelta(days=rng.randrange(0, 700))
            for expiry in futures_expiries(trade, 3) + [trade + timedelta(days=rng.randrange(10, 300))]:
                if futures_delivery(expiry) >= bond.maturity:
                    continue
                spot = rng.choice(YIELDS[4:-3])
                for strike in (spot - 0.5, spot, spot + 0.75):
                    for kind in ("call", "put"):
                        o = bond_option(bond, trade, expiry, spot, strike, rng.choice([6.5, 7.25, 8.1]),
                                        rng.choice([0.02, 0.06, 0.1, 0.14, 0.2]), kind)
                        row = asdict(o)
                        fwd = row.pop("forward")
                        row["forward_aip"], row["forward_ytm"] = fwd["aip"], fwd["ytm"]
                        row["spot_yield"], row["carry_rate"] = spot, fwd["carry_rate"]
                        rows.append({k: (iso(v) if isinstance(v, date) else v) for k, v in row.items()})
    return rows


def plain(obj):
    """A dataclass result as JSON-ready data, dates as ISO strings."""
    def conv(v):
        if isinstance(v, date):
            return iso(v)
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [conv(x) for x in v]
        return v
    return conv(asdict(obj))


# The page's worked example. Illustrative inputs: no market data.
EXAMPLE = {
    "bond": "R2035",
    "trade_date": date(2026, 10, 20),
    "ytm": 9.5,
    "nominal": 1_000_000,
    "carry": 7.0,
    "kind": "call",
    "price_vol": 0.08,
}


def curve_range(ytm):
    """The price-yield chart's yield axis: 5% to 15%, widened to keep the yield 2 points from an edge."""
    return min(5.0, float(int(ytm) - 2)), max(15.0, float(int(ytm) + 3))


def example(counts):
    e = EXAMPLE
    bond = BONDS[e["bond"]]
    settle = settlement_date(e["trade_date"])
    p = price(bond, settle, e["ytm"], nominal=e["nominal"])
    lo, hi = curve_range(e["ytm"])
    steps = int(round((hi - lo) / 0.05))
    curve = [[round(lo + i * 0.05, 2), price(bond, settle, round(lo + i * 0.05, 2)).aip] for i in range(steps + 1)]
    moves = []
    for bp in (-200, -100, 100, 200):
        moved = price(bond, settle, e["ytm"] + bp / 100)
        estimate = p.delta * bp / 100  # the duration tangent's price change
        moves.append({"bp": bp, "actual": moved.aip - p.aip, "duration": estimate,
                      "gap": moved.aip - p.aip - estimate})
    expiries = futures_expiries(e["trade_date"], 4)
    expiry = expiries[1]  # the second expiry: three to six months out
    f = forward(bond, settle, futures_delivery(expiry), e["ytm"], e["carry"])
    strike = round_half_up(f.ytm, 2)  # at the money forward, to the basis point
    o = bond_option(bond, e["trade_date"], expiry, e["ytm"], strike, e["carry"], e["price_vol"], e["kind"])
    # The spot yield at which the option is at the money: where the forward price equals the strike.
    # The chart centres on it, since its axis is the spot yield and the strike is a forward yield.
    carried = 1 + e["carry"] / 100 * f.days / 365
    atm_spot = implied_yield(bond, settle, (o.strike_aip + f.coupon_value) / carried)
    opt_curve = []
    for i in range(201):
        s = round(atm_spot - 2 + i * 0.02, 2)
        oi = bond_option(bond, e["trade_date"], expiry, s, strike, e["carry"], e["price_vol"], e["kind"])
        gain = oi.forward.aip - oi.strike_aip if e["kind"] == "call" else oi.strike_aip - oi.forward.aip
        # Intrinsic value against the forward, per contract: Black's value at zero volatility.
        opt_curve.append([s, oi.premium, oi.delta, max(gain, 0) * oi.notional / 100])
    opt = plain(o)
    opt.pop("forward")
    return {
        "generated_by": "scripts/make_vectors.py",
        "inputs": {**{k: (iso(v) if isinstance(v, date) else v) for k, v in e.items()}, "settle": iso(settle),
                   "expiry": iso(expiry), "strike": strike},
        "bond": plain(bond),
        "price": plain(p),
        "curve": {"x_min": lo, "x_max": hi, "points": curve},
        "moves": moves,
        "expiries": [iso(x) for x in expiries],
        "forward": plain(f),
        "option": opt,
        "option_curve": {"atm_spot": atm_spot, "x_min": opt_curve[0][0], "x_max": opt_curve[-1][0],
                         "points": opt_curve},
        "vector_counts": counts,
    }


def bonds_js():
    lines = [
        "// Generated by scripts/make_vectors.py from src/sabond/bonds.py. Don't edit by hand.",
        "// Sources: SOURCES.md.",
        "export const BONDS = {",
    ]
    for b in BONDS.values():
        lines.append(
            f'  {b.code}: {{ code: "{b.code}", coupon: {b.coupon!r}, maturity: "{iso(b.maturity)}", '
            f"coupon_dates: {json.dumps([list(x) for x in b.coupon_dates])}, "
            f"books_closed: {json.dumps([list(x) for x in b.books_closed])}, redemption: {b.redemption!r} }},"
        )
    lines.append("};")
    return "\n".join(lines) + "\n"


def build():
    rng = random.Random(20261020)
    prices = price_vectors(rng)
    vectors = {
        "generated_by": "scripts/make_vectors.py",
        "prices": prices,
        "yields": yield_vectors(rng, prices),
        "calendar": calendar_vectors(),
        "forwards": forward_vectors(rng),
        "options": option_vectors(rng),
    }
    counts = {
        "prices": len(vectors["prices"]),
        "yields": len(vectors["yields"]),
        "dates": len(vectors["calendar"]["settlement"]) + len(vectors["calendar"]["futures"]),
        "forwards": len(vectors["forwards"]),
        "options": len(vectors["options"]),
    }
    counts["total"] = sum(counts.values())
    return (bonds_js(), json.dumps(vectors, separators=(",", ":")) + "\n",
            json.dumps(example(counts), indent=1) + "\n")


def main():
    js, vec, ex = build()
    targets = {ROOT / "web" / "bonds.js": js, ROOT / "web" / "vectors.json": vec, ROOT / "web" / "example.json": ex}
    if "--check" in sys.argv:
        stale = [p.name for p, text in targets.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            sys.exit(f"Out of date: {', '.join(stale)}. Run python scripts/make_vectors.py")
        print("web/bonds.js, web/vectors.json and web/example.json are up to date.")
        return
    for p, text in targets.items():
        p.write_text(text, encoding="utf-8", newline="\n")
    v = json.loads(vec)
    print(f"Wrote web/bonds.js, web/example.json and web/vectors.json ({len(vec) / 1e6:.2f} MB): {len(v['prices'])} prices, "
          f"{len(v['yields'])} yields, {len(v['calendar']['settlement'])} settlement dates, "
          f"{len(v['forwards'])} forwards, {len(v['options'])} options.")


if __name__ == "__main__":
    main()
