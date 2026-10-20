"""Write the JavaScript port's bond table and test vectors from the Python package.

    python scripts/make_vectors.py          # write web/bonds.js and web/vectors.json
    python scripts/make_vectors.py --check  # fail if either file is out of date

The Python package is the source of truth. web/bonds.js is the bond table in JavaScript, and
web/vectors.json holds inputs and the Python's outputs for prices, implied yields, settlement and
futures dates, forwards and options. web/sabond.test.mjs checks the port against every vector.
Inputs are spread deterministically across every bond, edge dates (coupon and books-closed dates,
the last coupon period, leap days) and a wide range of yields. All yields are illustrative.
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
    return bonds_js(), json.dumps(vectors, separators=(",", ":")) + "\n"


def main():
    js, vec = build()
    targets = {ROOT / "web" / "bonds.js": js, ROOT / "web" / "vectors.json": vec}
    if "--check" in sys.argv:
        stale = [p.name for p, text in targets.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            sys.exit(f"Out of date: {', '.join(stale)}. Run python scripts/make_vectors.py")
        print("web/bonds.js and web/vectors.json are up to date.")
        return
    for p, text in targets.items():
        p.write_text(text, encoding="utf-8", newline="\n")
    v = json.loads(vec)
    print(f"Wrote web/bonds.js and web/vectors.json ({len(vec) / 1e6:.2f} MB): {len(v['prices'])} prices, "
          f"{len(v['yields'])} yields, {len(v['calendar']['settlement'])} settlement dates, "
          f"{len(v['forwards'])} forwards, {len(v['options'])} options.")


if __name__ == "__main__":
    main()
