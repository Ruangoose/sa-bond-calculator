"""The standard normal distribution.

The cumulative function uses Hart's (1968) double-precision rational approximation, as set out by
Graeme West in "Better approximations to cumulative normal functions" (Wilmott, 2005). It is
accurate to about 1e-14, needs nothing beyond exp(), and gives the same answer in Python and in the
JavaScript port, which has no erf() to lean on.
"""

from math import exp, pi, sqrt

_P = (
    0.0352624965998911,
    0.700383064443688,
    6.37396220353165,
    33.912866078383,
    112.079291497871,
    221.213596169931,
    220.206867912376,
)
_Q = (
    0.0883883476483184,
    1.75566716318264,
    16.064177579207,
    86.7807322029461,
    296.564248779674,
    637.333633378831,
    793.826512519948,
    440.413735824752,
)


def norm_cdf(x: float) -> float:
    """P(Z <= x) for a standard normal Z."""
    a = abs(x)
    if a > 37:
        tail = 0.0
    else:
        e = exp(-a * a / 2)
        if a < 7.07106781186547:
            num = _P[0]
            for c in _P[1:]:
                num = num * a + c
            den = _Q[0]
            for c in _Q[1:]:
                den = den * a + c
            tail = e * num / den
        else:
            b = a + 0.65
            for k in (4, 3, 2, 1):
                b = a + k / b
            tail = e / b / 2.506628274631
    return 1 - tail if x > 0 else tail


def norm_pdf(x: float) -> float:
    """The standard normal density."""
    return exp(-x * x / 2) / sqrt(2 * pi)
