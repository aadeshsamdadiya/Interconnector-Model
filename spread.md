# CLAUDE.md — Spread-Direct OU Model (Methodology 2)

This file provides guidance to Claude Code (claude.ai/code) when working with the spread-direct interconnector valuation notebook.

---

## Purpose

`IC_spread_direct.ipynb` is a second, independent methodology for IFA2 revenue simulation, built alongside `IC_descriptive_stats.ipynb` (Methodology 1). Both notebooks run the same Monte Carlo pipeline but differ in how they model the GB–France price relationship. Having both allows direct comparison and cross-validation.

---

## Why Two Methodologies?

**Methodology 1 (IC_descriptive_stats.ipynb)** follows Abadie & Chamorro (2021): model `log(P_GB)` and `log(P_FR)` as separate OU+jump processes, compute revenue as `|exp(f_GB + X_GB) − exp(f_FR + X_FR)|`.

This produced P50 = £305m/yr against Ofgem-disclosed IFA2 actuals of £108–188m/yr. The source of inflation is **Jensen's inequality**:

> E[|exp(X_GB) − exp(X_FR)|] >> |exp(E[X_GB]) − exp(E[X_FR])| when σ is large

Our log-price residual volatilities (σ_d_GB = 0.240, σ_d_FR = 0.421 per day) are driven up by the 2021–2022 energy crisis. Abadie's Spain-France data predates that crisis; their σ ≈ 0.05–0.10 so the inflation factor exp(σ²/2) ≈ 1.001 is negligible. Their methodology is not wrong — it breaks down in our high-volatility context.

**Methodology 2 (IC_spread_direct.ipynb)** models the spread directly in levels, following Cartea & González-Pedraz (2012). Crucially, this notebook **replicates Abadie's hourly reconstruction step**: the OLS is fitted on hourly spread data with 24 hour-of-day dummies, and for each simulated day the single daily OU value is combined with the 24 hourly OLS coefficients to reconstruct 24 hourly spreads, whose absolute values sum to the daily revenue.

No log transformation → no Jensen's inequality issue. All parameters estimated from price data.

---

## Model Structure

### Step 3′ — OLS on Hourly Spread Levels

- Regress hourly spread `S_{t,h}` (£/MWh) on: constant, trend τ, sin₁/cos₁ (annual Fourier terms), weekend dummy, 23 hour-of-day dummies (H01=midnight base, H02–H24)
- **36,984 hourly observations** (vs 1,546 daily obs in M1)
- Semi-annual terms (sin₂, cos₂) dropped: statistically significant on hourly data (sin₂ F=19.7, p<0.001) but economically small (~2 £/MWh amplitude vs σ=48 £/MWh), and projecting a 6-month cycle estimated over 4.5 years 25 years forward adds instability without meaningful revenue impact. Both AIC and BIC actually favour the full model (delta-BIC=+18 in favour of full) — they are dropped on economic grounds, not statistical.
- **Tau fix:** freeze tau feature at Jan 2025 (τ_anchor = 3.06 yrs, mid-point of 2024–2025 normalised period) rather than Mar 2026 (sample end). Mar 2026 is both a winter seasonal peak and the top of the 2023–2026 post-crisis rebound — anchoring there inflated the baseline by ~£11/MWh.
- `PROJ_TAU_GROWTH = 0.0` = flat nominal base case

**Estimated OLS (28 parameters: const, tau, sin₁, cos₁, weekend, H02–H24):**
- R²(hourly) = 0.1062, σ_resid(hourly) = 47.87 £/MWh, σ_resid(daily avg) = 33.50 £/MWh
- tau_est = +9.43 £/MWh/yr (OLS picks up spread widening as FR recovered post-crisis)
- Projected f_S yr1 daily mean: **£36.66/MWh** (anchored at Jan 2025, flat)
- Hourly peak (H19, evening): **+24.5 £/MWh** above midnight base
- Hourly trough (H08, morning): **−11.5 £/MWh** below midnight base
- Peak-to-trough daily swing: **~36 £/MWh** — the dominant within-day deterministic signal

### Step 4′ — Jump Detection on Daily-Averaged Spread Residuals

- Hourly OLS residuals **aggregated to daily means** for jump detection and OU estimation
- Cartea & González-Pedraz iterative ±3σ filter applied to daily-averaged residuals in **£/MWh**
- 72 jumps / 1,546 days
- Positive jumps (GB spike): n=27, mean λ=0.0170/day, β=109.2 £/MWh
- Negative jumps (FR spike): n=45, mean λ=0.0304/day, β=104.1 £/MWh

### Step 5′ — OU Estimation on Spread

- AR(1) on jump-cleaned daily-averaged residuals in levels
- φ = 0.633, κ = 167.0/yr, half-life = 1.5 days, σ_d = 18.16 £/MWh, θ ≈ 1.15 £/MWh
- Very fast mean reversion (half-life ~1.5 days) — explains the tight P10–P90 band in output

### Step 6′ — Monte Carlo with Hourly Reconstruction

- 10,000 paths × 25 years, daily Euler scheme, BATCH=500
- For each simulated day d, compute 24 hourly spreads: `S_{d,h} = f_S(d, h) + X_d`
  where `f_S(d, h)` comes from the `project_f_spread_hourly()` function (returns n_days × 24 array)
- Revenue: `Σ_h |S_{d,h}| × CAPACITY_MW × AVAILABILITY / 1e6 × capture_ratio` (£m/day)
- This replicates Abadie's step: *"transform the simulated daily log price series into hourly series by applying the hourly seasonality coefficients"*
- **AVAILABILITY = 0.9659** (96.59% per Ofgem IFA2 disclosure)
- **Base case: clean FA (no cannibalisation).** Cannibalisation is reserved as a scenario once Arup FA/MA figures for IFA2 and ENTSO-E TYNDP connection schedule are available.

### Capture Ratio

The Ofgem-disclosed figure is **gross congestion revenue net of market-related costs**. The theoretical `Σ_h|S_h| × capacity × availability` calculation ignores these deductions. The capture ratio is calibrated from 2024–2025 Ofgem actuals using the **hourly** theoretical denominator:

- Theoretical 2024 (hourly Σ|S_h|): £319.5m
- Theoretical 2025 (hourly Σ|S_h|): £360.5m
- Theoretical mean 2024–2025: £340.0m
- Actual mean 2024–2025: £108.5m (2024: £107.5m, 2025: £109.4m — 2023 excluded as anomalous)
- **Capture ratio: 0.319 (31.9%)**
- Interpretation: ~68% deducted as auction costs, TSO charges, balancing, and operational losses

**Why the hourly denominator matters:** Using hourly |S_h| and then summing captures within-day convexity (`E[|S_h|] > |E[S_h]|`). The daily-average approach (old version: 32.3%) conflated market costs with temporal aggregation artefacts. The hourly capture ratio now cleanly represents only genuine market-cost deductions.

**Important:** The capture ratio uses only 2024–2025 actuals to avoid the anomalous 2023 spread-widening year (France nuclear recovery). It is not a tuning parameter — it is a separate operational estimate applied multiplicatively. Actuals serve as validation, not calibration targets.

---

## Revenue Outputs (Methodology 2)

FA base case. AVAILABILITY = 0.9659. Capture ratio = 31.9% (2024–2025 hourly, normalised). No cannibalisation.

| Percentile | Yr 1 (2028) | Yr 5 (2032) | Yr 10 (2037) | Yr 25 (2052) |
|---|---|---|---|---|
| P10 | £111.1m | £111.1m | £110.9m | £111.3m |
| P50 | £123.3m | £123.4m | £123.2m | £123.5m |
| P90 | £137.9m | £137.8m | £137.3m | £138.1m |

Revenues are flat and stable — the fast mean-reverting spread OU (κ=167/yr, half-life 1.5 days) and flat f_S produce minimal year-to-year variation. The P10–P90 range (~£27m) is narrow. The P50 of £123m is consistent with the 2024–2025 Ofgem actuals of £107–109m given the capture ratio was calibrated from those figures.

---

## Comparison with Methodology 1

| | M1: Log-price OU | M2: Spread-direct OU (hourly) |
|---|---|---|
| Model | log(P_GB), log(P_FR) separate OU | S_{t,h} = f_S(t,h) + X_d hourly reconstruction |
| Jensen issue | Yes (σ large → inflated E[exp(X)]) | No (levels model) |
| Follows | Abadie & Chamorro (2021) | Cartea & González-Pedraz (2012) + Abadie hourly step |
| OLS data | Daily (1,546 obs) | Hourly (36,984 obs) with 23 hour dummies |
| Revenue computation | \|daily_mean\| × 24h | Σ_h \|S_h\| (24 hourly spreads per day) |
| Availability | 0.9659 | 0.9659 |
| Capture ratio applied | No | Yes (31.9%, from 2024–2025 hourly actuals) |
| P50 yr1 | £310m | £123m |
| Ofgem actuals 2022–25 | £108–188m | £108–188m (validation) |

---

## Ofgem Actuals (IFA2, Gross Congestion Revenue Net of Market Costs)

| Year | Revenue (£m) |
|---|---|
| 2022 | 134.9 |
| 2023 | 188.3 |
| 2024 | 107.5 |
| 2025 | 109.4 |

**Why 2023 > 2022 despite the nuclear crisis being in 2022:** The French nuclear crisis drove FR prices high, but the broader gas crisis drove GB prices high simultaneously — both markets moved together in 2022, compressing the GB–FR spread. In 2023, France's nuclear fleet recovered (prices fell) while GB remained gas-dependent (prices stayed elevated), widening the spread and boosting revenues. 2024–2025 reflect the normalised post-crisis structural spread.

---

## Key Open Questions

- **Capture ratio justification:** The ~68% deduction should be decomposed into auction costs, TSO charges, balancing, and operational losses. Ofgem publishes gross and net figures; the breakdown should be verified against those disclosures. The 31.9% ratio is derived from only 2 years (2024–2025) and may not hold across the 25-year regime.
- **Unidirectional vs bidirectional:** Model uses `|S_{t,h}|` (bidirectional). Confirm IFA2 earns revenue on both flow directions under its licence terms.
- **Cannibalisation (scenario, not base case):** Once Arup FA/MA figures for IFA2 (from the March 2024 report) and the ENTSO-E TYNDP 2022 connection schedule are available, add cannibalisation as a downside scenario using `f_adjusted(t,h) = f_S(t,h) − κ × GW_connected(t)`.
- **GB nuclear build:** Hinkley Point C (~2031) and Sizewell C will reduce GB prices, compressing the spread. Not currently modelled. Should be captured in the cannibalisation scenario or as a separate post-2031 spread adjustment.
- **Flat revenues:** The model produces identical revenues in 2028 and 2052 (half-life ~1.5 days means OU resets each day). Time variation only enters via f_S(t,h) — currently flat by design. Cannibalisation or a declining spread path would introduce the expected downward slope.
- **Semi-annual decision:** With hourly data, sin₂ is statistically significant (F=19.7, p<0.001) and both AIC and BIC prefer the full model. Dropped on economic grounds (amplitude ~2 £/MWh, potentially crisis-specific). Worth revisiting with a longer post-crisis data window.

---

## Files

| File | Description |
|---|---|
| `M2/IC_spread_direct.ipynb` | Source notebook — Methodology 2 (edit via build_notebook.py) |
| `M2/IC_spread_direct_executed.ipynb` | Last executed output (do not edit) |
| `M2/mc_revenue_spread_direct.csv` | P10/P50/P90 revenues, all 25 regime years |
| `M2/fig_eda.png` | 4-panel EDA: daily prices, spread, scatter, hourly profile |
| `M2/figS1_spread_ols.png` | Spread OLS fit and residuals |
| `M2/figS1c_hourly_profile.png` | Average spread by hour of day (motivates hour dummies) |
| `M2/figS2_methodology_comparison.png` | M1 vs M2 fan chart comparison |
| `M2/ic_cap_floor_m2_p10.xlsm` | Ofgem model with M2 P10 revenues in Input!V25:AT25 |
| `M2/ic_cap_floor_m2_p50.xlsm` | Ofgem model with M2 P50 revenues in Input!V25:AT25 |
| `M2/ic_cap_floor_m2_p90.xlsm` | Ofgem model with M2 P90 revenues in Input!V25:AT25 |
| `build_notebook.py` | Generates IC_spread_direct.ipynb — edit this, not the notebook |

---

## Python Environment

**Interpreter:** `/opt/anaconda3/bin/python3` (has nbformat, statsmodels, arch)
**Jupyter kernel:** Python 3 (ipykernel) — select in VS Code
**Generate notebook:**
```bash
cd /Users/aadesh/Documents/IC
/opt/anaconda3/bin/python3 build_notebook.py
```
**Execute notebook:**
```bash
/opt/anaconda3/bin/jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=900 \
  --ExecutePreprocessor.kernel_name=python3 \
  M2/IC_spread_direct.ipynb --output IC_spread_direct_executed.ipynb \
  --output-dir M2
```
