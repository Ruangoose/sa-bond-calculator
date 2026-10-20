"""Rounding as the JSE specification defines it: halves round away from zero.

Python's round() rounds halves to even, so it can't be used. Rounding works on the shortest decimal
form of the number (its repr), which is what a person reading the number sees. The JavaScript port
does the same with Number.prototype.toString(), which gives the same digits, so both sides round
identically.
"""

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(x: float, places: int) -> float:
    """Round x to `places` decimal places, halves away from zero. Never returns -0.0."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)) + 0.0
