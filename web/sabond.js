// sabond.js: a JavaScript port of the Python package `sabond`, for the browser.
//
// The Python package is the source of truth. This file mirrors it function for function, and
// sabond.test.mjs checks it against test vectors the Python writes (scripts/make_vectors.py).
// Field names in results match the Python's, which follow the JSE specification.
//
// Conventions, as in Python: yields, coupons and carry rates are percentages (7.5 means 7.5%),
// prices are per R100 nominal, volatilities are decimals (0.12 means 12%). Dates go in and come out
// as ISO strings ("2026-10-23"); inside, they are whole days since 1970-01-01, so there are no
// time-zone surprises.

import { BONDS } from "./bonds.js";

export { BONDS };

// ---- Dates -----------------------------------------------------------------------------------

const DAY_MS = 86400000;

export function dayOf(y, m, d) {
  return Math.round(Date.UTC(y, m - 1, d) / DAY_MS);
}

export function toDay(x) {
  if (typeof x === "number") return x;
  const [y, m, d] = x.split("-").map(Number);
  return dayOf(y, m, d);
}

export function toISO(day) {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

function ymd(day) {
  const t = new Date(day * DAY_MS);
  return [t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()];
}

const weekday = (day) => (((day + 3) % 7) + 7) % 7; // Monday 0 ... Sunday 6, as Python's weekday()

const isLeap = (y) => y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);

// ---- Rounding: halves away from zero, on the shortest decimal form (as Python's repr) ----------

export function roundHalfUp(x, places) {
  if (!Number.isFinite(x)) return x;
  const neg = x < 0;
  let [mant, exp] = Math.abs(x).toString().split("e");
  exp = exp ? parseInt(exp, 10) : 0;
  const [ip, fp = ""] = mant.split(".");
  let digits = ip + fp;
  let point = ip.length + exp;
  if (point <= 0) {
    digits = "0".repeat(1 - point) + digits;
    point = 1;
  }
  if (digits.length < point) digits += "0".repeat(point - digits.length);
  const keep = point + places;
  if (digits.length <= keep) return x;
  let head = BigInt(digits.slice(0, keep));
  if (digits.charCodeAt(keep) - 48 >= 5) head += 1n;
  let s = head.toString();
  if (places > 0) {
    s = s.padStart(places + 1, "0");
    s = s.slice(0, s.length - places) + "." + s.slice(s.length - places);
  }
  const v = Number(s);
  return neg && v !== 0 ? -v : v;
}

// ---- Normal distribution (Hart 1968, double precision, as in normal.py) ------------------------

const P = [0.0352624965998911, 0.700383064443688, 6.37396220353165, 33.912866078383, 112.079291497871,
  221.213596169931, 220.206867912376];
const Q = [0.0883883476483184, 1.75566716318264, 16.064177579207, 86.7807322029461, 296.564248779674,
  637.333633378831, 793.826512519948, 440.413735824752];

export function normCdf(x) {
  const a = Math.abs(x);
  let tail;
  if (a > 37) {
    tail = 0;
  } else {
    const e = Math.exp((-a * a) / 2);
    if (a < 7.07106781186547) {
      let num = P[0];
      for (let i = 1; i < P.length; i++) num = num * a + P[i];
      let den = Q[0];
      for (let i = 1; i < Q.length; i++) den = den * a + Q[i];
      tail = (e * num) / den;
    } else {
      let b = a + 0.65;
      for (const k of [4, 3, 2, 1]) b = a + k / b;
      tail = e / b / 2.506628274631;
    }
  }
  return x > 0 ? 1 - tail : tail;
}

export function normPdf(x) {
  return Math.exp((-x * x) / 2) / Math.sqrt(2 * Math.PI);
}

// ---- Business days (Public Holidays Act 36 of 1994, as in calendar.py) ------------------------

export function easterSunday(year) {
  const a = year % 19;
  const b = Math.floor(year / 100), c = year % 100;
  const d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return dayOf(year, Math.floor(n / 31), (n % 31) + 1);
}

const holidayCache = new Map();

export function publicHolidays(year) {
  if (holidayCache.has(year)) return holidayCache.get(year);
  const fixed = [[1, 1], [3, 21], [4, 27], [5, 1], [6, 16], [8, 9], [9, 24], [12, 16], [12, 25], [12, 26]]
    .map(([m, d]) => dayOf(year, m, d));
  const days = new Set(fixed);
  const easter = easterSunday(year);
  days.add(easter - 2); // Good Friday
  days.add(easter + 1); // Family Day
  for (const d of fixed) if (weekday(d) === 6) days.add(d + 1);
  holidayCache.set(year, days);
  return days;
}

export function isBusinessDay(day, extraHolidays = []) {
  day = toDay(day);
  return weekday(day) < 5 && !publicHolidays(ymd(day)[0]).has(day) && !extraHolidays.map(toDay).includes(day);
}

export function addBusinessDays(day, n, extraHolidays = []) {
  let d = toDay(day);
  const step = n >= 0 ? 1 : -1;
  let remaining = Math.abs(n);
  while (remaining) {
    d += step;
    if (isBusinessDay(d, extraHolidays)) remaining -= 1;
  }
  return toISO(d);
}

export function settlementDate(tradeDate, extraHolidays = []) {
  return addBusinessDays(tradeDate, 3, extraHolidays);
}

// ---- The JSE Bond Pricing Formula (as in jse.py; section numbers are the specification's) -------

export const PROUND = 5;
export const YROUND = 5;

function on(year, [day, month]) {
  if (month === 2 && day === 29 && !isLeap(year)) day = 28;
  return dayOf(year, month, day);
}

function bondOf(b) {
  return typeof b === "string" ? BONDS[b] : b;
}

export function timing(bond, settle) {
  bond = bondOf(bond);
  const s = toDay(settle);
  const mb = toDay(bond.maturity);
  if (s >= mb) throw new RangeError(`${bond.code} matures on ${bond.maturity}; settlement ${toISO(s)} is not before it`);
  const year = ymd(s)[0];
  const dates = [];
  for (let y = year - 1; y <= year + 1; y++) for (const dm of bond.coupon_dates) dates.push(on(y, dm));
  dates.sort((a, b) => a - b);
  const lcd = Math.max(...dates.filter((d) => d <= s));
  const ncd = Math.min(...dates.filter((d) => d > s));
  const [ny, nm] = ymd(ncd);
  const i = bond.coupon_dates.findIndex(([, m]) => m === nm);
  let bcd = on(ny, bond.books_closed[i]);
  if (bcd > ncd) bcd = on(ny - 1, bond.books_closed[i]);
  if (!(lcd < bcd && bcd <= ncd)) throw new RangeError(`${bond.code}: books-closed date not between LCD and NCD`);
  const n = roundHalfUp((mb - ncd) / (365.25 / 2), 0); // footnote 14
  const cumex = s < bcd ? 1 : 0;
  const daysAcc = cumex ? s - lcd : s - ncd;
  return { settle: s, lcd, ncd, bcd, n, cumex, days_acc: daysAcc, last_period: ncd === mb };
}

function values(bond, t, ytm) {
  const cpn = bond.coupon / 2;
  const cpnNcd = cpn * t.cumex;
  const r = bond.redemption;
  const n = t.n;
  const f = 1 / (1 + ytm / 200); // 3.9
  let bp, bpf, dbpf, d2bpf;
  if (!t.last_period) {
    bp = (t.ncd - t.settle) / (t.ncd - t.lcd);
    bpf = f ** bp;
    dbpf = (bp * bpf) / f;
    d2bpf = (dbpf * (bp - 1)) / f;
  } else {
    bp = (t.ncd - t.settle) / (365 / 2);
    bpf = f / (f + bp * (1 - f));
    dbpf = (bp * bpf ** 2) / f ** 2;
    d2bpf = (2 * dbpf * (bp * bpf - f)) / f ** 2;
  }
  const fn = f ** n;
  let annuity, dcpn, d2cpn;
  if (f !== 1) {
    annuity = (cpn * f * (1 - fn)) / (1 - f);
    dcpn = (cpn * (1 - (n - n * f + 1) * fn)) / (1 - f) ** 2;
    d2cpn = (cpn * (2 - (n * (1 - f) * (2 + (n - 1) * (1 - f)) + 2 * f) * f ** (n - 1))) / (1 - f) ** 3;
  } else {
    annuity = cpn * n;
    dcpn = (cpn * n * (n + 1)) / 2;
    d2cpn = (cpn * n * (n * n - 1)) / 3;
  }
  const dr = n * r * f ** (n - 1);
  const d2r = n * (n - 1) * r * f ** (n - 2);
  const body = cpnNcd + annuity + r * fn;
  const aip = bpf * body;
  const daip = dbpf * body + bpf * (dcpn + dr);
  const d2aip = d2bpf * body + 2 * dbpf * (dcpn + dr) + bpf * (d2cpn + d2r);
  return { f, bp, bpf, dbpf, d2bpf, aip, dcpn, d2cpn, dr, d2r, daip, d2aip };
}

export function price(bond, settle, ytm, nominal = null) {
  bond = bondOf(bond);
  const t = timing(bond, settle);
  const v = values(bond, t, ytm);
  const accrint = (t.days_acc * bond.coupon) / 365;
  const accrintR = roundHalfUp(accrint, PROUND);
  const cp = v.aip - accrint;
  const cpR = roundHalfUp(cp, PROUND);
  const aipR = roundHalfUp(cpR + accrintR, PROUND);
  const delta = (-(v.f ** 2) / 200) * v.daip;
  const dmod = (-100 * delta) / v.aip;
  const d2aipDy2 = (v.d2aip * v.f ** 4 + 2 * v.daip * v.f ** 3) / 40000;
  const out = {
    bond: bond.code, settle: toISO(t.settle), ytm,
    lcd: toISO(t.lcd), ncd: toISO(t.ncd), bcd: toISO(t.bcd), n: t.n, cumex: t.cumex, days_acc: t.days_acc,
    cpn: bond.coupon / 2, cpn_ncd: (bond.coupon / 2) * t.cumex,
    f: v.f, bp: v.bp, bpf: v.bpf, dbpf: v.dbpf, d2bpf: v.d2bpf,
    accrint, accrint_r: accrintR, aip: v.aip, cp, cp_r: cpR, aip_r: aipR,
    dcpn: v.dcpn, d2cpn: v.d2cpn, dr: v.dr, d2r: v.d2r, daip: v.daip, d2aip: v.d2aip,
    delta, rands_per_point: -100 * delta, dmod, dur: dmod / v.f, d2aip_dy2: d2aipDy2,
    conv: (10000 / v.aip) * d2aipDy2,
    nominal: null, int_consid: null, allin_consid: null, clean_consid: null,
  };
  if (nominal !== null) {
    const intConsid = roundHalfUp((accrintR * nominal) / 100, 2);
    const allinConsid = roundHalfUp((aipR * nominal) / 100, 2);
    Object.assign(out, {
      nominal, int_consid: intConsid, allin_consid: allinConsid,
      clean_consid: roundHalfUp(allinConsid - intConsid, 2),
    });
  }
  return out;
}

export function accruedInterest(bond, settle) {
  bond = bondOf(bond);
  const t = timing(bond, settle);
  return roundHalfUp((t.days_acc * bond.coupon) / 365, PROUND);
}

export class NoConvergence extends RangeError {}

export function impliedYield(bond, settle, aip, { y0 = 10, itnLim = 20, minY = -67, maxY = 200 } = {}) {
  bond = bondOf(bond);
  const t = timing(bond, settle);
  let y = y0;
  for (let i = 0; i <= itnLim; i++) {
    const v = values(bond, t, y);
    const diff = v.aip - aip;
    const nextF = v.f - diff / (v.daip - (diff * v.d2aip) / (2 * v.daip));
    const nextY = 200 / nextF - 200;
    if (!(minY <= nextY && nextY <= maxY)) break;
    const prev = roundHalfUp(y, YROUND);
    const opp = roundHalfUp(2 * nextY - y, YROUND);
    if (prev === opp) return opp;
    y = nextY;
  }
  throw new NoConvergence(`${bond.code}: no yield found for all-in price ${aip} on ${toISO(t.settle)}`);
}

// ---- Forwards and futures (as in carry.py) ----------------------------------------------------

export function couponsBetween(bond, after, through) {
  bond = bondOf(bond);
  const a = toDay(after), b = toDay(through), mb = toDay(bond.maturity);
  const out = [];
  for (let year = ymd(a)[0]; year <= ymd(b)[0] + 1; year++) {
    bond.coupon_dates.forEach((dm, i) => {
      const paid = on(year, dm);
      if (paid > mb) return;
      let closed = on(year, bond.books_closed[i]);
      if (closed > paid) closed = on(year - 1, bond.books_closed[i]);
      if (a < closed && closed <= b) out.push([paid, closed]);
    });
  }
  return out.sort((x, y) => x[0] - y[0]);
}

export function forward(bond, spotSettle, delivery, spotYield, carryRate) {
  bond = bondOf(bond);
  const s0 = toDay(spotSettle), s1 = toDay(delivery);
  if (s1 <= s0) throw new RangeError("delivery must be after spot settlement");
  if (s1 >= toDay(bond.maturity)) throw new RangeError(`${bond.code} matures on ${bond.maturity}, before delivery`);
  const r = carryRate / 100;
  const spotAip = price(bond, s0, spotYield).aip_r;
  const days = s1 - s0;
  const carried = spotAip * (1 + (r * days) / 365);
  const coupons = couponsBetween(bond, s0, s1).map(([paid, closed]) => {
    const amount = bond.coupon / 2;
    const value = paid <= s1 ? amount * (1 + (r * (s1 - paid)) / 365) : amount / (1 + (r * (paid - s1)) / 365);
    return { paid: toISO(paid), books_closed: toISO(closed), amount, value_at_delivery: value };
  });
  let couponValue = 0;
  for (const c of coupons) couponValue += c.value_at_delivery;
  const aip = carried - couponValue;
  return {
    bond: bond.code, spot_settle: toISO(s0), delivery: toISO(s1), spot_yield: spotYield, carry_rate: carryRate,
    spot_aip: spotAip, days, carried_aip: carried, coupons, coupon_value: couponValue, aip,
    ytm: impliedYield(bond, s1, aip),
  };
}

export function futuresExpiry(year, month, extraHolidays = []) {
  let d = dayOf(year, month, 1);
  d += (((3 - weekday(d)) % 7) + 7) % 7;
  while (!isBusinessDay(d, extraHolidays)) d += 7;
  return toISO(d);
}

export function futuresExpiries(after, count = 4, extraHolidays = []) {
  const a = toDay(after);
  const out = [];
  let year = ymd(a)[0];
  while (out.length < count) {
    for (const month of [2, 5, 8, 11]) {
      const d = futuresExpiry(year, month, extraHolidays);
      if (toDay(d) > a && out.length < count) out.push(d);
    }
    year += 1;
  }
  return out;
}

export function futuresDelivery(expiry, extraHolidays = []) {
  return addBusinessDays(expiry, 3, extraHolidays);
}

// ---- Options: Black (1976) on the forward all-in price (as in options.py) ----------------------

export function black76(fwd, strike, t, vol, kind = "call") {
  if (kind !== "call" && kind !== "put") throw new RangeError("kind must be 'call' or 'put'");
  if (t <= 0 || vol <= 0) throw new RangeError("time to expiry and volatility must be positive");
  const s = vol * Math.sqrt(t);
  const d1 = (Math.log(fwd / strike) + (s * s) / 2) / s;
  const d2 = d1 - s;
  let value, delta;
  if (kind === "call") {
    value = fwd * normCdf(d1) - strike * normCdf(d2);
    delta = normCdf(d1);
  } else {
    value = strike * normCdf(-d2) - fwd * normCdf(-d1);
    delta = normCdf(d1) - 1;
  }
  const pdf = normPdf(d1);
  return {
    value, delta, gamma: pdf / (fwd * s), vega: fwd * Math.sqrt(t) * pdf,
    theta: (-fwd * pdf * vol) / (2 * Math.sqrt(t)), d1, d2,
  };
}

export function bondOption(bond, tradeDate, expiry, spotYield, strikeYield, carryRate, priceVol, kind = "call",
  { notional = 100000, spotSettle = null, delivery = null, extraHolidays = [] } = {}) {
  bond = bondOf(bond);
  const trade = toDay(tradeDate), exp = toDay(expiry);
  if (exp <= trade) throw new RangeError("expiry must be after the trade date");
  spotSettle = spotSettle ?? settlementDate(trade, extraHolidays);
  delivery = delivery ?? addBusinessDays(exp, 3, extraHolidays);
  const fwd = forward(bond, spotSettle, delivery, spotYield, carryRate);
  const strikeAip = price(bond, delivery, strikeYield).aip_r;
  const t = (exp - trade) / 365;
  const b = black76(fwd.aip, strikeAip, t, priceVol, kind);
  const fwdDmod = price(bond, delivery, fwd.ytm).dmod;
  const scale = notional / 100;
  const spotDelta = price(bond, spotSettle, spotYield).delta;
  const dfwdDy = spotDelta * (1 + ((carryRate / 100) * fwd.days) / 365);
  return {
    bond: bond.code, kind, trade_date: toISO(trade), expiry: toISO(exp), t, forward: fwd,
    strike_yield: strikeYield, strike_aip: strikeAip, price_vol: priceVol,
    yield_vol: priceVol / ((fwdDmod * fwd.ytm) / 100), forward_dmod: fwdDmod, notional,
    value: b.value, premium: b.value * scale, delta: b.delta, delta_nominal: b.delta * notional,
    gamma: b.gamma, vega: (b.vega * scale) / 100, theta: (b.theta / 365) * scale,
    yield_delta: (b.delta * dfwdDy * scale) / 100,
  };
}

export function priceVolFromYieldVol(yieldVol, forwardDmod, forwardYtm) {
  return (yieldVol * forwardDmod * forwardYtm) / 100;
}
