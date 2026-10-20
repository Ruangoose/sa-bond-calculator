# Sources

Everything here is public. The documents are linked, not copied: the JSE's specification says it may
not be copied or distributed, and the rest are easier to cite at source. All were read on 20 October
2026.

## Method
- **JSE Bond Pricing Formula.** Bond Exchange of South Africa, "Bond Pricing Formula - Specifications",
  version 2 (final), 24 August 2005. Published by the JSE:
  https://jse.co.za/sites/default/files/media/documents/2019-04/BondPricingFormula-Final.pdf
  - `sabond/jse.py` follows it section by section, and `tests/test_jse_examples.py` checks both of its
    worked examples.
- **JSE bond futures.** JSE, "Futures on Nominal Bonds", product specification, December 2016:
  https://www.jse.co.za/sites/default/files/jse_document_manager/RW/Internal/Bond%20Futures/Nominal%20Bond%20Future%20Contract%20Spec.pdf
  - Expiry on the first business Thursday of February, May, August and November.
  - Quoted as a yield for settlement on the delivery date (expiry plus three business days), and
    settled at the all-in price from the JSE formula.
  - One contract is R100,000 nominal.
- **Black (1976).** Fischer Black, "The pricing of commodity contracts", *Journal of Financial
  Economics* 3 (1976), 167-179.
- **Normal distribution.** Hart's (1968) double-precision approximation, as given by Graeme West,
  "Better approximations to cumulative normal functions", *Wilmott Magazine* (2005).
- **Public holidays.** Public Holidays Act 36 of 1994 (South Africa): the Schedule's twelve holidays,
  and section 2(1), which moves a Sunday holiday to the Monday after it.

## Bond terms
- **The bond list.** National Treasury, "Schedule of domestic government bonds as at 30 September 2026":
  https://investor.treasury.gov.za/Debt%20Operations%20and%20Data/Schedule%20of%20Domestic%20Debt/Schedule%20of%20domestic%20government%20bonds%20as%20at%2030%20September%202026.pdf
  - Codes, coupons, interest dates and redemption dates.
  - R2044 and R2048 each redeem a third on three dates a year apart. The JSE convention prices them to
    the middle date (the specification's footnote 7).
  - The schedule prints R2030's interest dates as 28/02 & 31/08, which can't be right for a bond that
    matures on 31 January. R2030's terms of issue, and Treasury's interest payment notices, give
    31 January and 31 July:
    - https://sharedata.co.za/v2/scripts/SENS.aspx?id=520080 (25 July 2025);
    - https://sharedata.co.za/v2/scripts/SENS.aspx?id=537185 (26 January 2026).
- **Books-closed dates.** Each bond's terms of issue or applicable pricing supplement, published by
  National Treasury. Every one closes the register from ten days before each interest date. Treasury's
  folder of terms for fixed-rate bonds:
  https://investor.treasury.gov.za/Debt%20Operations%20and%20Data/Auction%20Related%20Information/Terms%20and%20conditions%20of%20issue/Fixed-rate%20bonds/
  - R2053's pricing supplement isn't in that folder; it is filed with the JSE:
    https://clientportal.jse.co.za/Content/JSEPricingSupplementsItems/R2053%20PricingSupplement1104.pdf

| Bonds | Coupon dates | Books close |
|---|---|---|
| R187, R188 | 21 Jun, 21 Dec | 11 Jun, 11 Dec |
| R2030, R2037, R2040, R2044 | 31 Jan, 31 Jul | 21 Jan, 21 Jul |
| R213, R2035, R214, R2048 | 28 Feb, 31 Aug | 18 Feb, 21 Aug |
| R2032, R2033, R209, R2038, R2039, R2042, R2053 | 31 Mar, 30 Sep | 21 Mar, 20 Sep |

## No market data
The package and its tests contain no market prices or yields. Yields are inputs. Any yield in an
example or a test is illustrative.
