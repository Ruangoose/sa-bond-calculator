// Checks the JavaScript port against every test vector the Python package writes.
// Run: node --test web/sabond.test.mjs   (regenerate vectors first: python scripts/make_vectors.py)
//
// Rounded results (prices to 5 decimals, considerations to the cent, yields to 5 decimals, dates)
// must match exactly. Unrounded results must agree to a relative 1e-11: far inside a cent on any
// contract, and loose enough for the last-bit differences between Python's and V8's pow().

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as sb from "./sabond.js";

const V = JSON.parse(readFileSync(new URL("./vectors.json", import.meta.url), "utf8"));
const REL = 1e-11;

function close(actual, expected, label) {
  const tol = REL * Math.max(1, Math.abs(expected));
  assert.ok(Math.abs(actual - expected) <= tol, `${label}: ${actual} vs ${expected}`);
}

function compare(actual, expected, exact, label) {
  for (const [k, e] of Object.entries(expected)) {
    if (!(k in actual)) continue;
    const a = actual[k];
    if (e === null || typeof e !== "number" || exact.has(k)) assert.deepEqual(a, e, `${label} ${k}`);
    else close(a, e, `${label} ${k}`);
  }
}

const PRICE_EXACT = new Set(["n", "cumex", "days_acc", "cpn", "cpn_ncd", "accrint_r", "cp_r", "aip_r", "nominal",
  "int_consid", "allin_consid", "clean_consid", "ytm"]);

test(`prices: ${V.prices.length} vectors`, () => {
  for (const e of V.prices) {
    const a = sb.price(e.bond, e.settle, e.ytm, e.nominal);
    compare(a, e, PRICE_EXACT, `${e.bond} ${e.settle} @${e.ytm}`);
  }
});

test(`implied yields: ${V.yields.length} vectors`, () => {
  for (const e of V.yields) {
    assert.equal(sb.impliedYield(e.bond, e.settle, e.aip), e.ytm, `${e.bond} ${e.settle} ${e.aip}`);
  }
});

test("settlement dates and futures dates", () => {
  for (const [trade, settle] of V.calendar.settlement) assert.equal(sb.settlementDate(trade), settle, trade);
  for (const [y, m, expiry, delivery] of V.calendar.futures) {
    assert.equal(sb.futuresExpiry(y, m), expiry, `${y}-${m}`);
    assert.equal(sb.futuresDelivery(expiry), delivery, expiry);
  }
  for (const [after, list] of V.calendar.next_expiries) assert.deepEqual(sb.futuresExpiries(after), list, after);
});

const FWD_EXACT = new Set(["spot_aip", "days", "ytm", "spot_yield", "carry_rate"]);

test(`forwards and futures: ${V.forwards.length} vectors`, () => {
  for (const e of V.forwards) {
    const a = sb.forward(e.bond, e.spot_settle, e.delivery, e.spot_yield, e.carry_rate);
    const label = `${e.bond} ${e.spot_settle}->${e.delivery}`;
    const { coupons, ...rest } = e;
    compare(a, rest, FWD_EXACT, label);
    assert.equal(a.coupons.length, coupons.length, `${label} coupons`);
    coupons.forEach((c, i) => compare(a.coupons[i], c, new Set(["amount"]), `${label} coupon ${i}`));
  }
});

const OPT_EXACT = new Set(["strike_aip", "notional", "forward_ytm", "strike_yield", "price_vol", "spot_yield",
  "carry_rate"]);

test(`options: ${V.options.length} vectors, premiums to the cent and far closer`, () => {
  let worst = 0;
  for (const e of V.options) {
    const a = sb.bondOption(e.bond, e.trade_date, e.expiry, e.spot_yield, e.strike_yield, e.carry_rate, e.price_vol,
      e.kind);
    const flat = { ...a, forward_aip: a.forward.aip, forward_ytm: a.forward.ytm, spot_yield: e.spot_yield,
      carry_rate: e.carry_rate };
    compare(flat, e, OPT_EXACT, `${e.bond} ${e.kind} ${e.strike_yield} ${e.expiry}`);
    worst = Math.max(worst, Math.abs(a.premium - e.premium));
  }
  assert.ok(worst < 0.005, `largest premium difference R${worst}`);
  console.log(`  largest premium difference: R${worst.toExponential(2)} per contract`);
});

test("the website's worked example (example.json)", () => {
  const E = JSON.parse(readFileSync(new URL("./example.json", import.meta.url), "utf8"));
  const i = E.inputs;
  assert.equal(sb.settlementDate(i.trade_date), i.settle);
  compare(sb.price(i.bond, i.settle, i.ytm, i.nominal), E.price, PRICE_EXACT, "example price");
  for (const [y, aip] of E.curve.points) close(sb.price(i.bond, i.settle, y).aip, aip, `curve ${y}`);
  assert.deepEqual(sb.futuresExpiries(i.trade_date, 4), E.expiries);
  const f = sb.forward(i.bond, i.settle, sb.futuresDelivery(i.expiry), i.ytm, i.carry);
  const { coupons, ...frest } = E.forward;
  compare(f, frest, FWD_EXACT, "example forward");
  assert.equal(f.coupons.length, coupons.length);
  const o = sb.bondOption(i.bond, i.trade_date, i.expiry, i.ytm, i.strike, i.carry, i.price_vol, i.kind);
  compare(o, E.option, OPT_EXACT, "example option");
  const carried = 1 + (i.carry / 100) * f.days / 365;
  assert.equal(sb.impliedYield(i.bond, i.settle, (o.strike_aip + f.coupon_value) / carried), E.option_curve.atm_spot);
  for (const [s, premium, delta, intrinsic] of E.option_curve.points) {
    const oi = sb.bondOption(i.bond, i.trade_date, i.expiry, s, i.strike, i.carry, i.price_vol, i.kind);
    close(oi.premium, premium, `option curve premium ${s}`);
    close(oi.delta, delta, `option curve delta ${s}`);
    const gain = i.kind === "call" ? oi.forward.aip - oi.strike_aip : oi.strike_aip - oi.forward.aip;
    close(Math.max(gain, 0) * oi.notional / 100, intrinsic, `option curve intrinsic ${s}`);
  }
});

test("rounding matches the specification's rule", () => {
  assert.equal(sb.roundHalfUp(131.648461227743, 5), 131.64846);
  assert.equal(sb.roundHalfUp(2.5, 0), 3);
  assert.equal(sb.roundHalfUp(-2.5, 0), -3);
  assert.equal(sb.roundHalfUp(1.005, 2), 1.01);
  assert.equal(sb.roundHalfUp(1e-7, 5), 0);
  assert.equal(sb.roundHalfUp(0.000015, 5), 0.00002);
});

test("the JSE's worked example 1, directly", () => {
  const r186 = { code: "R186", coupon: 10.5, maturity: "2026-12-21", coupon_dates: [[21, 6], [21, 12]],
    books_closed: [[11, 6], [11, 12]], redemption: 100 };
  const p = sb.price(r186, "2005-08-26", 7.5, 1500000);
  assert.equal(p.aip_r, 133.54709);
  assert.equal(p.cp_r, 131.64846);
  assert.equal(p.allin_consid, 2003206.35);
  assert.equal(sb.impliedYield(r186, "2005-08-26", 95.123456789), 11.34459);
});
