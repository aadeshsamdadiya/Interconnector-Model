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

**Methodology 2 (IC_spread_direct.ipynb)** models the spread directly in levels:

    S_t = P_GB_t − P_FR_t  (£/MWh, daily average)
    S_t = f_S(t) + X_t     (OLS deterministic + OU stochastic)

No log transformation → no Jensen's inequality issue. All parameters estimated from price data. Follows the Cartea & González-Pedraz (2012) framework more closely.

---

## Model Structure

### Step 3′ — OLS on Spread Levels
- Regress daily spread `S_t` (£/MWh) on: constant, trend τ, sin₁/cos₁ (annual Fourier terms only), weekend dummy
- Semi-annual terms (sin₂, cos₂) dropped following formal model comparison: individually insignificant (p = 0.09, 0.85) and a Spain-France artefact absent in GB-France. See `Reports/Seasonality_Analysis_GBFR.pdf`.
- No log, no hour dummies (daily data)
- **Tau fix:** freeze tau feature at Jan 2025 (τ_anchor = 3.06 yrs, mid-point of 2024–2025 normalised period) rather than Mar 2026 (sample end). Mar 2026 is both a winter seasonal peak and the top of the 2023–2026 post-crisis rebound — anchoring there inflated the baseline by ~£11/MWh.
- `PROJ_TAU_GROWTH = 0.0` = flat nominal base case

**Estimated OLS (5 parameters: const, tau, sin₁, cos₁, weekend):**
- R² = 0.140, σ_resid = 33.50 £/MWh
- tau_est = +9.43 £/MWh/yr (OLS picks up spread widening as FR recovered post-crisis)
- Projected f_S yr1 mean: **£36.65/MWh** (anchored at Jan 2025, flat)

### Step 4′ — Jump Detection on Spread Residuals
- Same Cartea & González-Pedraz iterative ±3σ filter applied to spread residuals in **£/MWh** (not log-units)
- 75 jumps / 1,546 days
- Positive jumps (GB spike): n=29, mean λ=0.0182/day, β=107.4 £/MWh
- Negative jumps (FR spike): n=46, mean λ=0.0310/day, β=103.3 £/MWh

### Step 5′ — OU Estimation on Spread
- AR(1) on jump-cleaned spread residuals in levels
- φ = 0.631, κ = 168.1/yr, σ_d = 17.97 £/MWh, θ ≈ 1.08 £/MWh (≈ 0, as expected since trend captured in f_S)
- Very fast mean reversion (κ = 168/yr ≈ reverts in ~2 days) — explains the tight P10–P90 band in output

### Step 6′ — Monte Carlo
- 10,000 paths × 25 years, daily Euler scheme, BATCH=500
- Spread OU: `X_{t+1} = c + φ·X_t + σ_d·ε_t + J_t`
- Revenue: `|f_S(t) + X_t| × 1,000 MW × 24h × 0.9659 × capture_ratio / 1e6` (£m/day, bidirectional)
- **AVAILABILITY = 0.9659** (96.59% per Ofgem IFA2 disclosure; updated from 0.95)
- **Base case: clean FA (no cannibalisation).** Cannibalisation is reserved as a scenario once Arup FA/MA figures for IFA2 and ENTSO-E TYNDP connection schedule are available.

### Capture Ratio
The Ofgem-disclosed figure is **gross congestion revenue net of market-related costs**. The theoretical `|spread| × capacity × hours` calculation ignores these deductions. A capture ratio is estimated from actuals and applied as a fixed parameter:

- Mean |spread| 2024–2025: £39.68/MWh (normalised post-crisis period only)
- Theoretical annual revenue (2024–2025): £335.7m (using AVAILABILITY=0.9659)
- Actual mean 2024–2025: £108.5m (2024: £107.5m, 2025: £109.4m — 2023 excluded as anomalous)
- **Capture ratio: 0.323 (32.3%)**
- Interpretation: ~68% deducted as auction costs, TSO charges, balancing, and operational losses

**Important:** The capture ratio uses only 2024–2025 actuals to avoid the anomalous 2023 spread-widening year (France nuclear recovery). It is not a tuning parameter — it is a separate operational estimate applied multiplicatively. Actuals serve as validation, not calibration targets.

---

## Revenue Outputs (Methodology 2)

FA base case. AVAILABILITY = 0.9659. Capture ratio = 32.3% (2024–2025 normalised). No cannibalisation.

| Percentile | Yr 1 (2028) | Yr 5 (2032) | Yr 10 (2037) | Yr 25 (2052) |
|---|---|---|---|---|
| P10 | £111.0m | £111.1m | £111.0m | £111.2m |
| P50 | £123.6m | £123.8m | £123.4m | £123.8m |
| P90 | £138.5m | £138.4m | £138.0m | £138.8m |

Revenues are flat and stable — the fast mean-reverting spread OU (κ=168/yr, reverts in ~2 days) and flat f_S produce minimal year-to-year variation. The P10–P90 range (£27m) is narrow. The P50 of £124m is consistent with the 2024–2025 Ofgem actuals of £107–109m given the capture ratio was calibrated from those figures.

---

## Comparison with Methodology 1

| | M1: Log-price OU | M2: Spread-direct OU |
|---|---|---|
| Model | log(P_GB), log(P_FR) separate OU | S_t = P_GB − P_FR direct OU |
| Jensen issue | Yes (σ large → inflated E[exp(X)]) | No (levels model) |
| Follows | Abadie & Chamorro (2021) | Cartea & González-Pedraz (2012) |
| Availability | 0.9659 | 0.9659 |
| Capture ratio applied | No | Yes (32.3%, from 2024–2025 actuals) |
| P50 yr1 | £310m | £124m |
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

- **Capture ratio justification:** The ~68% deduction should be decomposed into auction costs, TSO charges, balancing, and operational losses. Ofgem publishes gross and net figures; the breakdown should be verified against those disclosures. The 32.3% ratio is derived from only 2 years (2024–2025) and may not hold across the 25-year regime.
- **Unidirectional vs bidirectional:** Model uses `|S_t|` (bidirectional). Confirm IFA2 earns revenue on both flow directions under its licence terms.
- **Cannibalisation (scenario, not base case):** Once Arup FA/MA figures for IFA2 (from the March 2024 report) and the ENTSO-E TYNDP 2022 connection schedule are available, add cannibalisation as a downside scenario using `f_adjusted(t) = f_S(t) − κ × GW_connected(t)`.
- **GB nuclear build:** Hinkley Point C (~2031) and Sizewell C will reduce GB prices, compressing the spread. Not currently modelled. Should be captured in the cannibalisation scenario or as a separate post-2031 spread adjustment.
- **Flat revenues:** The model produces identical revenues in 2028 and 2052 (κ=168/yr means OU resets in ~2 days). Time variation only enters via f_S(t) — currently flat by design. Cannibalisation or a declining spread path would introduce the expected downward slope.

---

## Files

| File | Description |
|---|---|
| `IC_spread_direct.ipynb` | Source notebook — Methodology 2 (edit this) |
| `IC_spread_direct_executed.ipynb` | Last executed output (do not edit) |
| `mc_revenue_spread_direct.csv` | P10/P50/P90 revenues, all 25 regime years |
| `figS1_spread_ols.png` | Spread OLS fit and residuals |
| `figS2_methodology_comparison.png` | M1 vs M2 fan chart comparison |
| `ic_cap_floor_m2_p10.xlsm` | Ofgem model with M2 P10 revenues in Input!V25:AT25 |
| `ic_cap_floor_m2_p50.xlsm` | Ofgem model with M2 P50 revenues in Input!V25:AT25 |
| `ic_cap_floor_m2_p90.xlsm` | Ofgem model with M2 P90 revenues in Input!V25:AT25 |

---

## Python Environment

**Interpreter:** `/opt/homebrew/bin/python3.11`
**Jupyter kernel:** Python 3 (ipykernel) — select in VS Code
**Execute notebook:**
```bash
cd /Users/aadesh/Documents/IC
/opt/anaconda3/bin/jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=900 \
  --ExecutePreprocessor.kernel_name=python3 \
  IC_spread_direct.ipynb --output IC_spread_direct_executed.ipynb
```
