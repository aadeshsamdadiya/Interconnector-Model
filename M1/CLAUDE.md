# CLAUDE.md — IFA2 Bivariate OU Model (M1)

This file provides guidance to Claude Code when working in this directory.

## Working Files

| File | Purpose |
|------|---------|
| `build_bivariate_nb.py` | Python script that generates `IC_spread_bivariate_v1.ipynb` — edit this, then re-run |
| `IC_spread_bivariate_v1.ipynb` | Executed notebook — **do not hand-edit** |
| `figM1_revenue_fan.png` | Revenue fan chart output |

Rebuild and execute:
```bash
cd /Users/aadesh/Documents/IC/M1
/opt/homebrew/bin/python3.11 build_bivariate_nb.py
/opt/anaconda3/bin/jupyter-nbconvert --to notebook --execute --inplace IC_spread_bivariate_v1.ipynb --ExecutePreprocessor.timeout=600
```

---

## Model Overview

**Bivariate OU**: GB and FR electricity prices are modelled as two separate Ornstein-Uhlenbeck mean-reverting processes with correlated Brownian innovations (Abadie & Chamorro 2021). Spread = P_GB − P_FR.

**Contrast with M2**: M2 models the spread directly as a single OU process with Annex M / SP Global price-path assumptions. M1 makes no price-path assumption — parameters are estimated entirely from the data, and the simulation runs free.

→ See [`methodology.md`](methodology.md) for full model equations and parameter estimates.
→ M2 counterpart: [`../M2/IC_spread_direct_v2.ipynb`](../M2/IC_spread_direct_v2.ipynb)

---

## Section Map (`build_bivariate_nb.py`)

| § | Purpose | Key outputs |
|---|---------|-------------|
| 1 | Config + data load | `panel` (hourly, 2016/17-RPI-real), `daily` |
| 2 | Theta | `theta_gb`, `theta_fr` — full-sample unconditional means |
| 3 | Seasonal decomposition | `f_gb`, `f_fr` — Fourier seasonal fits; `z_gb`, `z_fr` — demeaned residuals |
| 4 | Jump detection + OU | `phi_gb`, `phi_fr`, `sig_gb`, `sig_fr`, `rho`, `chol` |
| 5 | Jump parameters | `jp_gb`, `jp_fr` — Poisson rates + exponential sizes |
| 6 | Diurnal shape | `spread_shape` — 24-hour within-day spread deviation |
| 7 | Monte Carlo | `annual_rev` [N_PATHS × N_PROJ_YEARS] in 2016/17-RPI-real £m |
| 8 | Revenue table | P10/P50/P90 per year |
| 9 | Physical ceiling check | Confirms no path exceeds max-spread × capacity ceiling |
| 10 | Fan chart | `figM1_revenue_fan.png` |
| 11 | W1 breach analysis | Annual and 5-yr NPV cap/floor breach probabilities (2016/17-RPI-real) |
| 12 | W3 breach analysis | Same converted to 2024-CPIH-real |
| 13 | W1 vs W3 summary | Side-by-side comparison table |

---

## Key Design Choices

**Full-sample estimation.** All parameters (theta, seasonal, OU, jumps, diurnal shape) are estimated on the complete Dec 2021 – Jul 2026 sample with no windowing or crisis filtering. The 2022 energy crisis is included; this inflates theta and sigma relative to a post-crisis calibration.

**No price-path assumptions.** There is no Annex M trajectory, no SP Global FR forecast, no convergence story. The long-run mean is the historical sample mean.

**Correlated simulation via Cholesky.** `[eps_GB, eps_FR] = chol([[1,rho],[rho,1]]) @ N(0,I)` at each daily step. rho estimated from jump-cleaned OU residuals.

**Independent jumps per region.** Poisson arrival + exponential size fitted separately for GB and FR. Jump union dates removed before AR(1) OU estimation.

**Revenue formula** (same as M2): `Σ_h |S(d,h)| × CAPACITY_MW × AVAILABILITY × CAPTURE_RATIO / 1e6` (GBPm/day).

**Price basis** (same as M2): 2016/17-RPI-real using FPA Input row 97 (CHAW, Jan 1987=100, base=264.992). Applied to raw panel before any fitting.

**Assessment periods**: P1=2021–25 (historical), P2=2026–30, P3=2031–35, P4=2036–40, P5=2041–45.

---

## Config Constants

| Constant | Value | Notes |
|----------|-------|-------|
| `N_PATHS` | 10,000 | MC paths |
| `PROJ_START_YEAR` | 2026 | First projection year |
| `N_PROJ_YEARS` | 20 | 2026–2045 |
| `CAPACITY_MW` | 1,000 | IFA2 nameplate |
| `AVAILABILITY` | 0.9659 | Same as M2 |
| `CAPTURE_RATIO` | 0.259 | Back-test mean CR from M2 §12 |
| `_RPI_1617` | 264.992 | CHAW base (2016/17) |
| `W1_CAP_REAL` | £61.6m | 2016/17-real (RPI-indexed → constant in real terms) |
| `W1_FLOOR_REAL` | £37.8m | Same |
| `W3_CAP_CPIH` | £79.885m | 2024-CPIH-real (PCL+PCAC from W3 template) |
| `W3_FLOOR_CPIH` | £49.956m | PFL+PCAF |
| `ODR` | 3.945% | Real operational discount rate |
