# sa-bond-calculator

South African government bonds, priced the way the market prices them:

- **Bonds:** the JSE Bond Pricing Formula. All-in and clean prices, accrued interest (including
  books-closed and ex-coupon), considerations, modified duration, convexity, and price to yield.
- **Forwards and futures:** cost of carry to a delivery date, converted back to a yield with the same
  formula. JSE bond futures expiry and delivery dates.
- **Options:** Black (1976) on the bond's forward all-in price, with Greeks. The strike is quoted as a
  yield and the volatility as a price volatility, as South African desks quote over-the-counter bond
  options.

It needs only the Python standard library. The tests check the package against both worked examples
in the JSE's specification, to the last printed digit of every rounded result.

A small JavaScript port in `web/` runs the same calculations in a browser. A Node test proves it
agrees with the Python on every test vector.

## Quick start

```python
from datetime import date
from sabond import BONDS, price, implied_yield, forward, bond_option, settlement_date

r2035 = BONDS["R2035"]
settle = settlement_date(date(2026, 10, 20))  # T+3: 23 October 2026

p = price(r2035, settle, 9.40, nominal=1_000_000)  # yield in %, illustrative
p.aip_r, p.cp_r, p.accrint_r  # all-in, clean, accrued, per R100 nominal
p.allin_consid  # rand
p.dmod, p.conv

implied_yield(r2035, settle, p.aip)  # back to 9.40

# A call on R2035 expiring with the February 2027 futures: strike 9.50%, carry 7.25%, price vol 11%
o = bond_option(r2035, date(2026, 10, 20), date(2027, 2, 4), 9.40, 9.50, 7.25, 0.11, "call")
o.premium, o.delta, o.vega, o.theta  # rand per R100,000 contract
```

## Rerun everything from a clean clone

Windows (PowerShell):

```powershell
.\check.ps1
```

That builds `.venv\` with pinned test dependencies, runs the Python tests, regenerates the test
vectors and runs the JavaScript tests. By hand:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts\make_vectors.py --check
node --test web/sabond.test.mjs
```

On macOS or Linux, run `./check.sh`. It needs Python 3.12 and Node 20 or later.

## In the browser

`web/sabond.js` is an ES module with the same functions (in camelCase) and the same result fields:

```js
import { price, bondOption, settlementDate } from "./sabond.js";

const p = price("R2035", settlementDate("2026-10-20"), 9.4);
const o = bondOption("R2035", "2026-10-20", "2027-02-04", 9.4, 9.5, 7.25, 0.11, "call");
```

It imports the bond table from `web/bonds.js`, which `scripts/make_vectors.py` writes from the Python.

## Layout

| Path | What it is |
|---|---|
| `src/sabond/jse.py` | The JSE Bond Pricing Formula |
| `src/sabond/carry.py` | Forwards, futures fair value, futures dates |
| `src/sabond/options.py` | Black (1976) and bond options |
| `src/sabond/bonds.py` | The bonds in issue, with sources |
| `src/sabond/calendar.py` | Business days and T+3 settlement |
| `tests/` | pytest suite, including the JSE's worked examples |
| `scripts/make_vectors.py` | Writes `web/bonds.js` and the test vectors |
| `web/` | The JavaScript port and its Node test |

## Method

See [METHOD.md](METHOD.md) for the conventions and [SOURCES.md](SOURCES.md) for every source.

## Not advice

This is a calculator. It holds no market data: every yield, rate and volatility is an input, and any
in the examples is illustrative. Nothing here is investment advice.

## Licence

MIT. See [LICENSE](LICENSE).
