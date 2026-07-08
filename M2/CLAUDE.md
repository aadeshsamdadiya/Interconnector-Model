# CLAUDE.md — IFA2 Spread-Direct OU Model

This file provides guidance to Claude Code when working in this directory.

## Working File

`IC_spread_direct_v2.ipynb` — run all sections sequentially; each depends on prior outputs.
Python 3.11 (Homebrew): `/opt/homebrew/bin/python3.11`
Output directory: `/Users/aadesh/Documents/IC/M2/`

---

## Section Map

| §  | Purpose | Key outputs |
|----|---------|-------------|
| 1–2 | Config + data load | `panel` (hourly GB/FR/spread), `ACTUALS`, `CFFM2_RPIt` |
| 3 | Cleaning & alignment | Aligned hourly panel, gap-filled (<4 h linear, else drop) |
| 4–5 | Descriptive stats + EDA | ADF tests, spread distribution, against-price flow analysis |
| 6–9 | OLS f_S estimation | `params_spread`, `hourly_spread_resid`, `proj_dates`, `fs_proj` |
| 10 | Jump detection | `jump_dates`, `jump_cleaned` (daily residual ex-jumps), `jump_params` |
| 11 | OU+jump NLS | `ou_s`: phi, kappa, sigma_d, c, jump beta/lambda per quarter |
| 12 | Back-test | `CAPTURE_RATIO` (mean audited turnover / simulated gross over test years) |
| 13 | MC f_S projection | `fs_hourly_proj` (hourly deterministic shape, tau frozen) |
| 14 | Annex M scenarios | `adj_df`: annual spread delta per scenario vs panel anchor |
| 15 | Monte Carlo | `annual_rev` [N_PATHS × N_PROJ_YEARS] 2016/17-real £m; `p10`, `p50`, `p90`; simulates S_t = f_S + X_t + Y_t |
| 16 | Revenue tables + charts | Fan charts, scenario P50 comparison |
| 17 | Export → W1 Excel | `ifa2_pcr_p{10,50,90}.xlsm` written to OUTPUT_DIR |
| 18 | Accounts analysis | Revenue waterfall vs audited ACTUALS; RAV reconstruction |
| 19 | W1 breach analysis | Annual and 5-yr NPV cap/floor breach probabilities |
| 21 | W3 breach analysis | Same as §19 but in 2024-CPIH-real; exports W3 xlsm copies |
| 22 | Equity returns | Annual FCFE yield, NI/FCFE IRR for W1 and W3; `equity_returns_fcfe.png` |
| 20 | Summary | Markdown narrative only — no computed outputs |

---

## Key Design Choices

**Spread modelled directly** (GB − FR in GBP/MWh), not log-prices. Eliminates Jensen's
inequality bias from E[exp(X)] > exp(E[X]) that inflated revenues in the log-price approach.

**Revenue = |spread|** — IFA2 earns whether GB>FR or FR>GB (bidirectional implicit flow).

**Two-stage price basis pipeline.** Historical prices (nominal) are deflated to 2016/17-RPI-real
before OLS using `_RPI_1617 / _HIST_RPI[yr]` (see `data.md §5`). Annex M projections are in
2024-GDP-real (not CPI-real) and require a second conversion: `adj_t = GDP_cum_t × RPI_1617 / RPI_t`
(see `data.md §2`). Skipping either step puts the spread in the wrong price basis relative to cap/floor.

**Tau zeroed in projection, f_S demeaned.** The OLS linear trend captures the 2022 energy
crisis spike (+9.45 GBP/MWh/yr) and must not be extrapolated. In §13, `tau` is set to 0.0
and f_S is demeaned year-by-year (annual mean forced to ~0 GBP/MWh). f_S then carries only
the within-year shape: Fourier seasonality, hour dummies, weekend dummy. Annex M
`spread_level[d]` in §15 is the **absolute** annual mean spread (not a delta from an anchor).
OU process X_t mean-reverts to c_ou (≈ 0).

**Effects-coded hour dummies (sum-to-zero).** H01–H23 columns take +1 when active, −1 when
hour=23 (the reference hour). `b0` in the OLS is the grand mean of the spread across all 24
hours — not the H24 baseline. H24 coefficient = −Σ(H01..H23 params). Standard indicator
coding (0/1) would give different coefficients and a different `b0` interpretation.

**Holiday dummy requires external file.** `D_t` (weekend + public holiday) depends on
`Fixed_Public_Holidays_GB_France.xlsx` (GB and France fixed public holidays by month/day).
See `data.md §3`.

**Capture ratio (CR)** bridges model gross spread to Ofgem-assessed net revenue. Estimated
out-of-sample in §12. Not a Tobit/censoring model — IFA2 commits capacity day-ahead and
cannot refuse individual hours; there is no hourly decision right to censor.

**No Cholesky** — single spread OU process, not bivariate GB/FR. Correlation structure
is implicitly embedded in the historical spread residuals.

**Tax = 25%** applied to EBIT (current UK corporation tax rate). FCFE = NI + Dep − RplCap.

---

## Regulatory Framework

### Window 1 — `iFA2CFFM2_PCR_decision.xlsm`

| Action | Sheet | Row | Cols | Notes |
|--------|-------|-----|------|-------|
| Write ARt (assessed revenue) | `Costs & Revenue` | 29 | 16–40 | Op yr 1–25 (2021–2045); values nominal (real × RPIt) |
| Read CLt (cap) | `Revenue Adjustment` | 11 | 1–45 | Nominal; deflate by RPIt before breach test |
| Read FLt (floor) | `Revenue Adjustment` | 12 | 1–45 | Same |
| Read op year labels | `Revenue Adjustment` | 5 | 1–45 | Map: calendar year = 2020 + op_yr |
| Read RPIt | `Indexation` | 11 | 1–45 | Row 5 = year label; row 11 = index value |
| Read ODR | `Assessment` | 13 | — | Real operational discount rate |
| Read W1 OPEX + Dep | `Allowances Cap` | — | — | For §22; controllable + non-controllable combined |
| Read Opening RAV + RplCap | `Op RAV` | — | — | For §22; Op RAV yr1 = investment base incl. IDC |

Three output copies: `ifa2_pcr_p10.xlsm`, `ifa2_pcr_p50.xlsm`, `ifa2_pcr_p90.xlsm`.

### Window 3 — `iFA2CFFM2_PCR_decision_W3.xlsm`

| Action | Sheet | Row | Col(s) | Notes |
|--------|-------|-----|--------|-------|
| Read PCL | `Inputs` | 25 | I | Preliminary Cap Level (2024-CPIH-real £m) |
| Read PFL | `Inputs` | 26 | I | Preliminary Floor Level |
| Read PCAC | `Inputs` | 27 | I | Cap PCA adjustment (can be negative) |
| Read PCAF | `Inputs` | 28 | I | Floor PCA adjustment |
| Read ctrl OPEX | `Inputs` | 35 | P–AN | Op yrs 1–25 (2024-CPIH-real £m) |
| Read non-ctrl OPEX | `Inputs` | 36 | P–AN | Op yrs 1–25 |
| Write ARt | `Costs & Revenue` | 29 | 16–40 | In 2024-CPIH-real (not nominal) |
| Write CPIHt | `Inputs` | 145 | 16–40 | CPIHt = CPIH_yr / 132.9 per op year |

cap = PCL + PCAC; floor = PFL + PCAF (read fresh from Excel each time parameters change).
W3 Op RAV sheet absent — W3 RAV approximated as W1_RAV × RPIt / CPIHt in §22.
Three output copies: `ifa2_w3_pcr_p{10,50,90}.xlsm`.

### Equity Returns (§22) — `IFA2CFFM1_PCR_decision.xlsm`

W1 OPEX, Dep, RAV, and RplCap arrays are hardcoded in §22 from this file (25 values each,
op yrs 1–25). Re-extract if the W1 cost model changes. Investment base = Opening Op RAV yr1
(includes IDC capitalised 2016–2021). W3 OPEX from W3 Inputs rows 35–36 also hardcoded.

→ See [`methodology.md`](methodology.md) for model equations.
→ See [`data.md`](data.md) for data sources, file paths, and all config values.
