"""
IFA2 Equity Returns — Annual cash to equity investor.

FCFE = Net income + Depreciation - Replacement capex
     = (Revenue - OPEX - Dep)(1-tax) + Dep   [replacement capex excluded; small vs FCFE]

Denominator = Opening operational RAV year 1:
  W1: £404.16m  (16/17-RPI-real)  — includes IDC capitalised during 2016-21 construction
  W3: ~£518m    (2024-CPIH-real)  — W1 RAV converted via RPIt/CPIHt; approximate

Two revenue columns per window:
  UNCAPPED  — raw MC revenue, no regulatory intervention
  CAPPED    — effective revenue after cap/floor clipping (what IFA2 actually receives)
"""

import numpy as np
import numpy_financial as nf

# ── Year / price-level setup ─────────────────────────────────────────────────
YEARS = list(range(2021, 2046))
RPIt  = {yr: 1.3772 * (1.0324 ** (yr - 2026)) for yr in YEARS}   # 16/17-real → nominal
_CH   = {2019:107.4, 2020:108.0, 2021:113.1, 2022:120.6, 2023:126.1, 2024:132.9}
CPIHt = {yr: (_CH[yr] if yr in _CH else 132.9*(1.025**(yr-2024)))/132.9 for yr in YEARS}

# ── Revenue functions ────────────────────────────────────────────────────────
ACTUALS_NOM = {2022: 69.6, 2023: 100.8, 2024: 101.6, 2025: 72.2}
MC = {
    'p50': {2026:96.01,2027:78.32,2028:75.10,2029:68.33,2030:65.45,
            2031:63.62,2032:63.06,2033:62.64,2034:62.52,2035:62.38,
            2036:62.79,2037:62.53,2038:62.38,2039:62.58,2040:63.33,
            2041:65.19,2042:69.08,2043:70.83,2044:75.35,2045:78.93},
    'p10': {2026:86.39,2027:69.76,2028:66.73,2029:60.49,2030:57.95,
            2031:56.22,2032:55.80,2033:55.35,2034:55.36,2035:55.22,
            2036:55.44,2037:55.25,2038:55.21,2039:55.30,2040:55.99,
            2041:57.66,2042:61.10,2043:62.66,2044:66.76,2045:70.20},
    'p90': {2026:107.07,2027:88.50,2028:85.09,2029:77.94,2030:74.74,
            2031:72.86,2032:72.18,2033:71.51,2034:71.74,2035:71.50,
            2036:72.03,2037:71.78,2038:71.28,2039:72.10,2040:72.55,
            2041:74.67,2042:78.59,2043:80.58,2044:85.40,2045:89.37},
}

def rev_w1(yr, sc):
    if yr in ACTUALS_NOM: return ACTUALS_NOM[yr] / RPIt[yr]
    return MC[sc].get(yr)

def rev_w3(yr, sc):
    r = rev_w1(yr, sc)
    return None if r is None else r * RPIt[yr] / CPIHt[yr]

# ── Regulatory bounds ────────────────────────────────────────────────────────
W1_CAP, W1_FLR = 61.6,  37.8    # 16/17-RPI-real, £m
W3_CAP, W3_FLR = 90.363, 84.264 # 2024-CPIH-real, £m

# ── W1 costs (16/17-RPI-real, £m) from IFA2CFFM1_PCR_decision.xlsm ─────────
_W1_OPEX = [15.503,11.901,15.875,15.581,16.551,16.494,16.311,17.490,17.825,18.748,
            18.423,18.444,18.463,18.486,19.264,18.785,18.810,18.843,18.868,19.662,
            19.236,19.268,19.304,19.342,19.534]
_W1_DEP  = [16.166,16.166,16.166,16.166,16.166,16.166,16.166,16.303,16.504,16.504,
            16.579,16.579,16.632,16.729,17.085,17.085,17.085,20.023,20.023,20.023,
            20.249,20.863,20.863,20.863,20.863]
_W1_RAV  = [404.16,387.99,371.83,355.66,339.49,323.33,307.16,293.45,280.56,264.06,
            248.69,232.11,216.22,200.75,187.94,170.85,153.77,160.18,140.16,120.14,
            101.25, 83.45, 62.59, 41.73, 20.86]
# Replacement capex from Op RAV (non-zero years only; small vs FCFE)
_W1_RCAP = {2027:2.455, 2028:3.416, 2030:1.131, 2031:0.690,
            2032:1.162, 2033:3.921, 2037:23.501, 2040:1.131, 2041:2.455}

W1_OPEX = {yr: _W1_OPEX[i] for i,yr in enumerate(YEARS)}
W1_DEP  = {yr: _W1_DEP[i]  for i,yr in enumerate(YEARS)}
W1_RAV  = {yr: _W1_RAV[i]  for i,yr in enumerate(YEARS)}
W1_RCAP = {yr: _W1_RCAP.get(yr, 0.0) for yr in YEARS}

# Opening RAV for "return on investment" denominator
W1_INIT = _W1_RAV[0]   # £404.16m — includes IDC capitalised during construction

# ── W3 costs (2024-CPIH-real, £m) from iFA2CFFM2_PCR_decision_W3.xlsm ──────
_W3_CTRL  = [17.155,11.849,14.766,14.796,15.515,15.441,15.608,16.589,17.077,17.697,
             17.464,17.495,17.526,17.746,18.220,17.876,17.911,17.947,18.176,18.675,
             18.371,18.412,18.454,18.537,14.018]
_W3_NCTRL = [1.324,1.046,1.036,1.026,1.016,1.007,0.997,0.988,0.979,0.970,
             0.960,0.951,0.943,0.934,0.925,0.916,0.908,0.899,0.891,0.882,
             0.874,0.866,0.858,0.850,0.633]
W3_OPEX = {yr: _W3_CTRL[i]+_W3_NCTRL[i] for i,yr in enumerate(YEARS)}
W3_DEP  = {yr: W1_DEP[yr]  * RPIt[yr] / CPIHt[yr] for yr in YEARS}
W3_RAV  = {yr: _W1_RAV[i]  * RPIt[yr] / CPIHt[yr] for i,yr in enumerate(YEARS)}
W3_RCAP = {yr: _W1_RCAP.get(yr, 0.0) * RPIt[yr] / CPIHt[yr] for yr in YEARS}
W3_INIT = W3_RAV[2021]  # ≈ £475m; approximate — W3 Op RAV sheet not available

TAX = 0.25

# ── Core P&L for one year ────────────────────────────────────────────────────
def yr_pl(rev_raw, opex, dep, rcap, cap, flr):
    """Return dict of P&L items for uncapped and capped scenarios."""
    rev_eff = max(flr, min(rev_raw, cap))
    def _calc(rev):
        ebit = rev - opex - dep
        ni   = ebit * (1 - TAX) if ebit > 0 else ebit   # no tax relief on losses assumed
        fcfe = ni + dep - rcap
        return ni, fcfe
    ni_u, fcfe_u = _calc(rev_raw)
    ni_c, fcfe_c = _calc(rev_eff)
    return dict(rev_raw=rev_raw, rev_eff=rev_eff, opex=opex, dep=dep, rcap=rcap,
                ni_u=ni_u, fcfe_u=fcfe_u, ni_c=ni_c, fcfe_c=fcfe_c)

def run(rev_fn, opex_d, dep_d, rav_d, rcap_d, cap, flr, sc):
    rows = []
    for yr in YEARS:
        r = rev_fn(yr, sc)
        if r is None: continue
        p = yr_pl(r, opex_d[yr], dep_d[yr], rcap_d[yr], cap, flr)
        p.update(yr=yr, ry=yr-2020, rav=rav_d[yr])
        rows.append(p)
    return rows

# ── IRR helper ───────────────────────────────────────────────────────────────
def irr(cfs):
    try:    return nf.irr(cfs) * 100
    except: return float('nan')

# ── Print one window ─────────────────────────────────────────────────────────
def print_window(label, rows, init, cap_name, flr_name, basis):
    W = 130
    print(f"\n  {'─'*W}")
    print(f"  {label}   basis={basis}  |  Initial investment = £{init:.1f}m  |  cap={cap_name}  floor={flr_name}")
    print(f"  {'─'*W}")

    # Header
    h = (f"  {'Yr':>3} {'Cal':>4}  "
         f"{'RevRaw':>8} {'RevEff':>8}  "
         f"{'OPEX':>7} {'Dep':>7} {'RplCap':>7}  "
         f"── UNCAPPED ──────────────  "
         f"── REGULATED (capped/floored) ────────────────────────────────")
    print(h)
    h2 = (f"  {'':>3} {'':>4}  "
          f"{'':>8} {'':>8}  "
          f"{'':>7} {'':>7} {'':>7}  "
          f"{'NI':>8} {'FCFE':>8} {'Yld%':>6}  "
          f"{'NI':>8} {'FCFE':>8} {'Yld%':>6}  "
          f"{'NI diff':>8} {'Δ cap impact':>12}")
    print(h2)
    print(f"  {'─'*W}")

    for r in rows:
        cf = '▲' if r['rev_raw'] > cap_name else ('▼' if r['rev_raw'] < flr_name else ' ')
        # yield on original investment
        yld_u = r['fcfe_u'] / init * 100
        yld_c = r['fcfe_c'] / init * 100
        ni_diff = r['ni_c'] - r['ni_u']  # negative = cap cost to investor
        print(f"  {r['ry']:>3} {r['yr']:>4}  "
              f"{r['rev_raw']:>8.1f} {cf}{r['rev_eff']:>7.1f}  "
              f"{r['opex']:>7.2f} {r['dep']:>7.2f} {r['rcap']:>7.2f}  "
              f"{r['ni_u']:>8.2f} {r['fcfe_u']:>8.2f} {yld_u:>5.1f}%  "
              f"{r['ni_c']:>8.2f} {r['fcfe_c']:>8.2f} {yld_c:>5.1f}%  "
              f"{ni_diff:>+8.2f} {'(cap cost)' if ni_diff < -0.5 else ('(flr gain)' if ni_diff > 0.5 else ''):>12}")

    print(f"  {'─'*W}")
    avgs = {k: np.mean([r[k] for r in rows]) for k in ['fcfe_u','fcfe_c','ni_u','ni_c']}
    print(f"  {'AVERAGE':>52}  "
          f"{avgs['ni_u']:>8.2f} {avgs['fcfe_u']:>8.2f} {avgs['fcfe_u']/init*100:>5.1f}%  "
          f"{avgs['ni_c']:>8.2f} {avgs['fcfe_c']:>8.2f} {avgs['fcfe_c']/init*100:>5.1f}%")

    # IRR rows
    cfs_fu = [-init] + [r['fcfe_u'] for r in rows]
    cfs_fc = [-init] + [r['fcfe_c'] for r in rows]
    cfs_nu = [-init] + [r['ni_u']   for r in rows]
    cfs_nc = [-init] + [r['ni_c']   for r in rows]
    print(f"\n  IRR on investment of £{init:.0f}m:")
    print(f"    FCFE  uncapped: {irr(cfs_fu):>6.2f}%   "
          f"FCFE  capped: {irr(cfs_fc):>6.2f}%   "
          f"(FCFE = Net income + Dep − replacement capex)")
    print(f"    NI    uncapped: {irr(cfs_nu):>6.2f}%   "
          f"NI    capped: {irr(cfs_nc):>6.2f}%   "
          f"(NI = profit only; dep recovery not counted)")

# ── Main ─────────────────────────────────────────────────────────────────────
for sc, slabel in [('p50','P50 base'), ('p10','P10 downside'), ('p90','P90 upside')]:
    print(f"\n{'='*130}")
    print(f"  SCENARIO: {slabel}")
    print(f"  All £m in real terms.  Tax = 25% on EBIT.  Dep added back to FCFE (non-cash).")
    print(f"  Yld% = FCFE / Opening RAV year 1 (= investor's annual cash-on-investment yield).")
    print(f"{'='*130}")

    w1r = run(rev_w1, W1_OPEX, W1_DEP, W1_RAV, W1_RCAP, W1_CAP, W1_FLR, sc)
    print_window("WINDOW 1", w1r, W1_INIT, W1_CAP, W1_FLR, "16/17-RPI-real")

    w3r = run(rev_w3, W3_OPEX, W3_DEP, W3_RAV, W3_RCAP, W3_CAP, W3_FLR, sc)
    print_window("WINDOW 3 [W3 RAV ≈ estimated]", w3r, W3_INIT, W3_CAP, W3_FLR, "2024-CPIH-real")

# ── Summary across scenarios ─────────────────────────────────────────────────
print(f"\n\n{'='*80}")
print("  IRR SUMMARY  (on Opening RAV = investment inc. IDC during construction)")
print(f"{'='*80}")
print(f"  {'':20}   W1 (16/17-real, init=£{W1_INIT:.0f}m)          W3 (2024-CPIH-real, init≈£{W3_INIT:.0f}m)")
print(f"  {'Scenario':20}   {'NI unc':>8} {'NI cap':>8} {'FCFE unc':>10} {'FCFE cap':>10}   "
      f"{'NI unc':>8} {'NI cap':>8} {'FCFE unc':>10} {'FCFE cap':>10}")
print(f"  {'─'*78}")
for sc, sl in [('p10','P10'),('p50','P50'),('p90','P90')]:
    w1r = run(rev_w1,W1_OPEX,W1_DEP,W1_RAV,W1_RCAP,W1_CAP,W1_FLR,sc)
    w3r = run(rev_w3,W3_OPEX,W3_DEP,W3_RAV,W3_RCAP,W3_CAP,W3_FLR,sc)
    def _irr(rows, key): return irr([-W1_INIT if key.startswith('') else -W1_INIT]
                                    + [r[key] for r in rows])
    i1nu = irr([-W1_INIT]+[r['ni_u']   for r in w1r])
    i1nc = irr([-W1_INIT]+[r['ni_c']   for r in w1r])
    i1fu = irr([-W1_INIT]+[r['fcfe_u'] for r in w1r])
    i1fc = irr([-W1_INIT]+[r['fcfe_c'] for r in w1r])
    i3nu = irr([-W3_INIT]+[r['ni_u']   for r in w3r])
    i3nc = irr([-W3_INIT]+[r['ni_c']   for r in w3r])
    i3fu = irr([-W3_INIT]+[r['fcfe_u'] for r in w3r])
    i3fc = irr([-W3_INIT]+[r['fcfe_c'] for r in w3r])
    print(f"  {sl:20}   {i1nu:>7.2f}% {i1nc:>7.2f}% {i1fu:>9.2f}% {i1fc:>9.2f}%   "
          f"{i3nu:>7.2f}% {i3nc:>7.2f}% {i3fu:>9.2f}% {i3fc:>9.2f}%")
print(f"  {'─'*78}")
print(f"\n  NI IRR    = discount rate making NPV(net income stream) = initial investment")
print(f"  FCFE IRR  = same but cash flow = net income + dep − replacement capex")
print(f"            = what equity holder physically receives each year")
print(f"  Cap/floor = W1: [{W1_FLR:.0f}, {W1_CAP:.0f}]  W3: [{W3_FLR:.1f}, {W3_CAP:.1f}] (all in respective real £m)")
print(f"  Ofgem allowed returns: W1 cap 8.1%, W3 cap 7.42%, W3 floor 3.55% (real, post-tax on RAV)")
print(f"  UK Gilt real yield benchmark: ~1.8%.  W1 FCFE capped IRR ≈ 8%; W3 FCFE capped IRR ≈ 11%.")
