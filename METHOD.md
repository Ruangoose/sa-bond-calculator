# Method

Units throughout: yields, coupons and the carry rate are percentages (7.5 means 7.5%), prices are per
R100 nominal, and volatilities are decimals (0.12 means 12%).

## Bonds: the JSE Bond Pricing Formula
`sabond/jse.py` follows the JSE's specification (BESA, version 2, 24 August 2005), and its comments
give the section numbers. In short:

- **Dates.** For a settlement date S: the last coupon date on or before S, the next coupon date after
  it, and the books-closed date for that next coupon (ten days before it, for every bond in the list).
  N counts the coupons after the next one, up to and including maturity.
- **Cum or ex.** The bond trades ex interest from its books-closed date. The next coupon then goes to
  the seller, and accrued interest is negative.
- **All-in price.** Discount the next coupon (if cum), the remaining coupons and the redemption at the
  semi-annual yield, then discount back over the broken period. That period is the fraction of the
  current coupon period still to run. In its last six months a bond is priced like a money-market
  instrument instead: simple interest, actual/365.
- **Accrued interest** is actual/365 on the annual coupon, so it isn't exactly half a coupon over a
  coupon period. Clean prices can therefore move a few cents across a books-closed date, one of the
  formula's known quirks.
- **Rounding.** The clean price is rounded to 5 decimals, and so is accrued interest. The all-in
  price is the sum of the two. Considerations are rounded to the cent. Halves round away from zero.
- **Risk.** Delta, modified duration, duration and convexity come from the formula's own derivatives,
  as in section 6 of the specification.
- **Price to yield.** Bailey's method, as the specification recommends, with the yield rounded to 5
  decimals.

## Dates
- Settlement is T+3 business days.
- Business days exclude weekends and the public holidays in the Public Holidays Act, with a Sunday
  holiday moved to the Monday. One-off declared holidays aren't built in; pass them in where they
  matter.
- JSE bond futures expire on the first business Thursday of February, May, August and November. The
  bond is delivered three business days later.

## Forwards and futures: cost of carry
- **Forward price.** The spot all-in price is carried to the delivery date at the carry (repo) rate,
  simple, actual/365. Coupons the holder collects over that period are subtracted:
  - a coupon is collected if its books close after spot settlement and on or before delivery;
  - one paid by delivery is carried to delivery at the same rate;
  - one paid after delivery is discounted back to it.
- **Forward yield.** The forward all-in price converts back to a yield with the JSE formula for the
  delivery date. That is the futures fair value, since JSE bond futures are quoted as yields for the
  delivery date.

## Options: Black (1976) on the forward all-in price
This is how South African desks price over-the-counter options on government bonds.
- **Underlying.** The forward all-in price for delivery three business days after expiry, as above.
- **Strike.** Quoted as a yield, and converted to an all-in price for the same delivery date with the
  JSE formula.
- **Volatility.** A price volatility. The equivalent yield volatility shown alongside is the price
  volatility divided by (modified duration × yield), both at the forward yield.
- **Time.** Calendar days from trade date to expiry, divided by 365.
- **Premium.** Black's value with no discounting factor. Per contract, it scales by the contract's
  nominal over 100; the default contract is R100,000 nominal, the JSE's contract size.
- **Calls and puts are on price.** A call gains when yields fall.
- **Greeks**, per contract:
  - delta: to the forward price, so 0 to 1 for a call;
  - vega: rand per volatility point;
  - theta: rand per calendar day, from the time-decay term alone (there is no discounting to decay);
  - yield delta: rand for a 1 basis-point rise in the spot yield.

## How it's checked
- **The JSE's examples.** `tests/test_jse_examples.py` reproduces both worked examples in the
  specification:
  - every intermediate value, to the 13 or more significant figures printed;
  - every rounded price and consideration, exactly;
  - the implied-yield iteration, step by step.
- **The other tests** cover:
  - the conventions across every bond: coupon counts, cum and ex, coupon dates, 28 February in leap
    years, and the last coupon period against the specification's money-market formula;
  - price-to-yield round trips;
  - derivatives against finite differences;
  - the calendar, including the JSE's own futures dates;
  - carry, and Black's model (put-call parity and the Greeks).
- **The JavaScript port.** `scripts/make_vectors.py` writes inputs and the Python's outputs to
  `web/vectors.json`, and `web/sabond.test.mjs` checks the port against every one. Rounded results
  must match exactly, and unrounded ones to a relative 1e-11.
