# IFA_2 Interconnector Valuation — Project Context

## Goal
Build a quantitative equity valuation model for **IFA_2**, a proposed 1 GW GB–France HVDC interconnector, under **Ofgem's Cap & Floor regulatory regime (Window 3)**.

The model simulates 25-year hourly revenues under 10,000 Monte Carlo paths of the GB–France price spread and produces equity metrics (floor/cap breach probabilities, IRR distribution, Revenue at Risk, Upside Capture Ratio) that can be used in an equity investment decision.

---

## Regulatory Context
- **Cap & Floor (Window 3):** Ofgem guarantees a revenue floor (downside protection) and caps upside. The equity value corridor is the P50 spread revenue minus the floor.
- **Equity benchmark:** IRR > 10.1% or ≥ 200–375 bps above 10-year UK gilt yield (RIIO-3 Finance Annex).
- **Capacity:** 1,000 MW. Revenue = spread × capacity × availability × hours.

---

## Project Flow (Interconnectors_Equity_focus document)

| Step | Description | Status |
|------|-------------|--------|
| 1 | Data — GB/FR hourly prices, FX, Ofgem cap/floor, Arup FA/MA revenues, ENTSO-E schedule | ✅ Done |
| 2 | Descriptive statistics — spread construction, Abadie Table 1 & 3, ADF tests, hourly seasonality plots | ✅ Done |
| 3 | Deterministic component — OLS estimation of f_t (trend, annual/semi-annual seasonality, weekend dummy, 24-hour pattern) for GB and FR separately | ✅ Done |
| 4 | Jump detection — Cartea & González-Pedraz iterative filter; separate positive/negative jumps; exponential size estimation; seasonal intensities | ✅ Done |
| 5 | OU estimation — AR(1) on jump-cleaned residuals; mean reversion speeds (α^GB, α^FR), diffusion volatilities (σ^GB, σ^FR), correlation ρ | ✅ Done |
| 6 | Monte Carlo — 10,000 paths × 25 years; Euler discretisation of OU+jump processes; Cholesky for correlation | ✅ Done |
| 7 | Revenue projections — P10/P50/P90 annual revenues (£m nominal) written to Ofgem Cap & Floor Excel model; floor/cap breach recalculates in Excel | ✅ Done |
| 8 | Driver attribution — Shapley decomposition; scenario analysis (Bull/Base/Bear) across: trend, cannibalism, jumps, regime-switching vol, Hinkley, GB-FR correlation, wind CfD | ⬜ |

---

## Core Methodology
- **Primary paper:** Abadie & Chamorro (2021), *Energy* 233, 121177 — "Evaluation of a cross-border electricity interconnection: The case of Spain-France"
  - Log-prices decomposed into deterministic f_t + stochastic X_t (OU with jumps)
  - f_t: OLS with annual/semi-annual Fourier terms, linear trend, weekend/holiday dummy, 24 hourly dummies (Eq. 2)
  - X_t: OU mean-reverting process with Poisson compound jump term (Eqs. 3–4)
  - Monte Carlo via Euler discretisation (Eq. 6)
- **Jump factor structure:** Cartea & González-Pedraz (2012), *Energy Economics* 34 — two-sided jump factor Y_t (separate positive/negative Poisson arrivals with exponential sizes)
- **Spread modelled directly** as GB_GBP − FR_GBP (not log-spread), consistent with Cartea's interconnector valuation framework

---

## Stochastic Model (for reference in later steps)

```
log P^i_t = f^i(t) + X^i_t

f^i(t) = b1 sin(2πt) + b2 cos(2πt)          # annual seasonality
        + b3 sin(4πt) + b4 cos(4πt)          # semi-annual seasonality
        + b5 t + b6 D^i_t                     # trend + weekend/holiday dummy
        + b7 + Σ b_j H_{j-7,t}  (j=8..31)   # constant + 24 hourly dummies

dX^i_t = (α^i − κ^i X^i_t) dt + σ^i dW^i_t + J^i(μ^i_j, σ^i_j) dq^i_t

E[dW^GB dW^FR] = ρ dt                        # correlated Brownian motions
```

---

## Data
All files in `/Users/aadesh/Documents/IC/`:

| File | Description |
|------|-------------|
| `Cleaned_GBFR.xlsx` | Main data file |
| → `GB_FINAL` | GB N2EX hourly day-ahead prices, GBP/MWh (Dec 2021–Mar 2026) |
| → `FR_FINAL` | FR EPEX hourly day-ahead prices, EUR/MWh (Jan 2021–Mar 2026) |
| → `GBP-EUR` | Bloomberg EURGBP daily FX rate; column "EUR/GBP" = GBP per 1 EUR |
| `FR-SP.pdf` | Abadie & Chamorro (2021) — primary methodology paper |
| `1-s2.0-S0140988311001241-main.pdf` | Cartea & González-Pedraz (2012) — jump factor paper |
| `Interconnectors_Equity focus.docx` | Project flow document (full step-by-step outline) |

**FX convention:** `FR_price_GBP = FR_price_EUR × fx_eur_gbp` (multiply, not divide).  
**GB prices:** already in GBP/MWh. **FR prices:** EUR/MWh, converted via FX.  
**Spread:** `spread_gbp = gb_price_gbp − fr_price_gbp`

---

## Code
All scripts in `/Users/aadesh/Documents/IC/`:

| File | Purpose |
|------|---------|
| `IC_descriptive_stats.ipynb` | **Main notebook — Steps 1–7** (use this going forward) |
| `aquind_descriptive_stats.py` | Standalone script — Steps 1–2 only (superseded) |
| `aquind_descriptive_stats.ipynb` | Notebook — Steps 1–2 only (superseded) |
| `table1_hourly_stats.csv` | Abadie Table 1 analogue (hourly) |
| `table2_daily_stats.csv` | Abadie Table 3 analogue (daily) |
| `adf_tests.csv` | ADF unit-root test results |
| `mc_revenue_projections.csv` | P10/P50/P90/mean revenues, all 25 regime years |
| `fig1_daily_prices.png` | Daily GB and FR spot prices |
| `fig2_daily_spread.png` | Daily GB−FR spread |
| `fig3_hourly_seasonality.png` | Empirical hourly log-price seasonality |
| `fig4_revenue_fan_chart.png` | Monte Carlo revenue fan chart (P10/P50/P90) |
| `ic_cap_floor_p10.xlsm` | Ofgem Cap & Floor model — P10 revenue inputs |
| `ic_cap_floor_p50.xlsm` | Ofgem Cap & Floor model — P50 revenue inputs |
| `ic_cap_floor_p90.xlsm` | Ofgem Cap & Floor model — P90 revenue inputs |

**Python environment:** `/opt/homebrew/bin/python3.11`  
**Key packages:** pandas, numpy, scipy, statsmodels, matplotlib  
**Jupyter kernel:** select Python 3.11 (Homebrew) in VS Code

---

## Key Empirical Findings (Step 2)
- **Data window:** 2021-12-09 → 2026-03-03 (36,984 hourly obs, 1,546 days)
- **Mean spread:** 28.2 GBP/MWh (GB structurally above FR)
- **Hourly spread excess kurtosis:** 292.6 (daily: 8.1) — fat tails, jump-consistent
- **Hourly spread skewness:** −1.37 — left-skewed, large negative spikes (FR > GB during 2022 nuclear outages)
- **ADF:** GB price and spread reject unit root at 1%; FR price borderline (p=0.064) — expect rejection after f_t removed in Step 3
- **Fig 3:** France shows wider hourly amplitude than GB (±0.50 vs ±0.35 log units), informing larger hourly dummy coefficients in OLS

---

## Model Outputs (Steps 3–7)

### OLS (Step 3)
- **GB:** R²=0.276, σ_resid=0.630, tau_est=−0.274/yr (−24%/yr — 2022 crisis artefact, not extrapolated)
- **FR:** R²=0.322, σ_resid=1.035, tau_est=−0.528/yr (−41%/yr — same)
- **Tau fix:** tau feature frozen at sample-end value (τ_end ≈ 4.233 yrs) → projects at Mar 2026 post-crisis price levels. `PROJ_TAU_GROWTH = 0.0` (flat nominal). Set to 0.02 for 2%/yr bullish scenario.
- **Projected f(t):** GB yr1 = £56/MWh, FR yr1 = £22/MWh → deterministic spread = £33.6/MWh

### Jump Detection (Step 4)
- Cartea & González-Pedraz iterative ±3σ filter on daily residuals; separate positive/negative jumps with quarterly Poisson λ and exponential β per country

### OU Estimation (Step 5)
- AR(1) on jump-cleaned daily residuals; OU correlation ρ between GB and FR innovations estimated from residual series

### Monte Carlo (Step 6)
- 10,000 paths × 25 years; daily Euler scheme; BATCH=500; Cholesky correlation; revenue = |P_GB − P_FR| × 1000 MW × 24h × 0.95 / 1e6 (£m/day, bidirectional)

### Revenue Projections (Step 7)
| Percentile | Yr 1 | Yr 5 | Yr 13 | Yr 25 |
|---|---|---|---|---|
| P10 | £262.2m | £261.7m | £261.6m | £261.7m |
| P50 | £304.8m | £304.8m | £304.5m | £304.8m |
| P90 | £423.6m | £427.1m | £430.6m | £423.9m |

Revenues are flat across the 25-year regime (flat nominal base case). Stable P50 ≈ £305m/yr is consistent with: 1 GW × 0.95 × 24h × £33.6/MWh × 365 ≈ £280m deterministic + stochastic uplift from |spread| convexity.

### Excel Outputs
Three copies of the Ofgem Cap & Floor model written to `IC/`:
- `ic_cap_floor_p10.xlsm` — Input!V25:AT25 populated with P10 revenues
- `ic_cap_floor_p50.xlsm` — Input!V25:AT25 populated with P50 revenues
- `ic_cap_floor_p90.xlsm` — Input!V25:AT25 populated with P90 revenues

Open in Excel (not Numbers) — cap/floor breach recalculates via VBA/formulas on the Assessment sheet.

### Code
All Steps 3–7 are in notebook cells of `IC_descriptive_stats.ipynb` (cells after the Step 2 section).  
Supporting output: `mc_revenue_projections.csv`, `fig4_revenue_fan_chart.png`.
