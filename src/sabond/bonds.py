"""Bond terms, and the South African fixed-rate government bonds in issue.

A bond is what the JSE specification calls BOND(MB, CB, RB, CpnDates, BcDates): a maturity date, an
annual coupon (as a percentage), a redemption amount per R100 nominal, and the day and month of its
two coupon dates and its two books-closed dates.

Sources for the bond list (see SOURCES.md for links and dates):
- Codes, coupons, interest dates and redemption dates: National Treasury, "Schedule of domestic
  government bonds as at 30 September 2026".
- R2030's interest dates: that schedule prints 28/02 & 31/08, which can't be right for a bond
  maturing on 31 January. National Treasury's interest payment notices pay R2030 on 31 January and
  31 July (SENS, 25 July 2025 and 26 January 2026), so those dates are used.
- R2044 and R2048 redeem in three equal parts a year apart. The JSE convention prices them to the
  middle date (the specification's footnote 7).
- Books-closed dates: each bond's terms of issue or applicable pricing supplement (National
  Treasury). Every one closes the register from ten days before each interest date.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Bond:
    code: str
    coupon: float  # annual coupon, % of nominal (CB)
    maturity: date  # the deemed redemption date (MB)
    coupon_dates: tuple[tuple[int, int], tuple[int, int]]  # (day, month), in calendar order
    books_closed: tuple[tuple[int, int], tuple[int, int]]  # (day, month), paired with coupon_dates
    redemption: float = 100.0  # RB, per R100 nominal

    def __post_init__(self):
        if (self.maturity.day, self.maturity.month) not in self.coupon_dates and not (
            self.maturity.month == 2 and (29, 2) in self.coupon_dates
        ):
            raise ValueError(f"{self.code}: maturity {self.maturity} is not a coupon date")


# Coupon and books-closed patterns: (coupon dates, books-closed dates).
_JUN_DEC_21 = (((21, 6), (21, 12)), ((11, 6), (11, 12)))
_JAN_JUL_31 = (((31, 1), (31, 7)), ((21, 1), (21, 7)))
_FEB_AUG = (((28, 2), (31, 8)), ((18, 2), (21, 8)))
_MAR_SEP = (((31, 3), (30, 9)), ((21, 3), (20, 9)))

_TABLE = [
    # code, coupon %, maturity, pattern
    ("R187", 10.5, date(2026, 12, 21), _JUN_DEC_21),
    ("R188", 10.5, date(2027, 12, 21), _JUN_DEC_21),
    ("R2030", 8.0, date(2030, 1, 31), _JAN_JUL_31),
    ("R213", 7.0, date(2031, 2, 28), _FEB_AUG),
    ("R2032", 8.25, date(2032, 3, 31), _MAR_SEP),
    ("R2033", 10.0, date(2033, 3, 31), _MAR_SEP),
    ("R2035", 8.875, date(2035, 2, 28), _FEB_AUG),
    ("R209", 6.25, date(2036, 3, 31), _MAR_SEP),
    ("R2037", 8.5, date(2037, 1, 31), _JAN_JUL_31),
    ("R2038", 10.875, date(2038, 3, 31), _MAR_SEP),
    ("R2039", 9.875, date(2039, 3, 31), _MAR_SEP),
    ("R2040", 9.0, date(2040, 1, 31), _JAN_JUL_31),
    ("R214", 6.5, date(2041, 2, 28), _FEB_AUG),
    ("R2042", 10.125, date(2042, 3, 31), _MAR_SEP),
    ("R2044", 8.75, date(2044, 1, 31), _JAN_JUL_31),
    ("R2048", 8.75, date(2048, 2, 28), _FEB_AUG),
    ("R2053", 11.625, date(2053, 3, 31), _MAR_SEP),
]

BONDS: dict[str, Bond] = {
    code: Bond(code, coupon, maturity, pattern[0], pattern[1])
    for code, coupon, maturity, pattern in _TABLE
}

# Bonds that redeem in parts: the redemption dates, of which the middle one is the maturity above.
REDEMPTION_DATES = {
    "R2044": (date(2043, 1, 31), date(2044, 1, 31), date(2045, 1, 31)),
    "R2048": (date(2047, 2, 28), date(2048, 2, 28), date(2049, 2, 28)),
}
