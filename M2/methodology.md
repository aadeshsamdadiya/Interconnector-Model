# Methodology — IFA2 Spread-Direct OU Model

Primary reference: Abadie & Chamorro (2021), *Energy* 233, 121177.
Jump structure: Cartea & González-Pedraz (2012), *Energy Economics* 34.

---

## 0. Historical Price Deflation (§3, applied before any estimation)

Nominal GB and FR prices from `GB-FR07.xlsx` are deflated to **2016/17-RPI-real** immediately after panel construction, before OLS or OU estimation:

```
deflator[yr] = RPI_1617 / HIST_RPI[yr]        RPI_1617 = 264.992
```

Applied simultaneously to GB price, FR price (post-FX), and spread. Source: FPA model Input sheet row 97 (CHAW, Jan 1987=100). Full `HIST_RPI` table in `data.md §5`. This ensures all estimation works on the same price basis as the Annex M projected spreads and the regulatory cap/floor.

---

## 1. Spread Decomposition

```
S_t = f_S(t, h) + X_t
```

- **S_t** — hourly GB−FR spread (GBP/MWh); constructed as `GB_price − FR_price_EUR × fx_eur_gbp`, then RPI-deflated (§0 above)
- **f_S(t, h)** — deterministic seasonal + trend component, estimated by OLS on hourly data
- **X_t** — stochastic daily OU residual (jump-cleaned)

Revenue per day:
```
rev_d = Σ_{h=1}^{24} |S_{d,h}| × CAPACITY_MW × AVAILABILITY / 1e6 × CAPTURE_RATIO  (£m)
```

---

## 2. Deterministic Component f_S(t, h)

OLS on all hourly observations (§6–9). **Full specification (all candidate terms):**

```
f_S(t, h) = b0 + b1·τ
           + b2·sin(2πτ) + b3·cos(2πτ)        ← annual harmonics
           + b4·sin(4πτ) + b5·cos(4πτ)        ← semi-annual harmonics
           + b6·D_t
           + Σ_{h=0}^{22} b_h·H_{h,t}
```

| Term | Description |
|------|-------------|
| τ | Years since `t0_spread` = `daily.index[0]` (first historical day, ≈ Dec 2021). Formula: `(timestamp − t0).total_seconds() / (365.25 × 24 × 3600)`. This is **not** `ANCHOR_DATE` in the config. |
| sin(2πτ), cos(2πτ) | Annual Fourier harmonics (same τ variable) |
| sin(4πτ), cos(4πτ) | Semi-annual Fourier harmonics |
| D_t | Weekend + public holiday dummy (1 = Saturday, Sunday, **or** GB/FR public holiday). Requires `Fixed_Public_Holidays_GB_France.xlsx`; see `data.md §3`. |
| H_{h,t} | **23 effects-coded (sum-to-zero) hour dummies.** Hours 0–22 estimated; hour 23 is the reference. Column value = **+1** if current hour = h, **−1 if current hour = 23**, 0 otherwise. `b0` = grand mean of spread across all 24 hours (not tied to hour 23). H24 coefficient derived via constraint: `b_H24 = −Σ(b_H01 .. b_H23)`. |

**Hypothesis tests (§8) — five tests determine the final specification:**

| Test | H0 | Method | Decision |
|------|----|--------|----------|
| 1 | All Fourier terms = 0 jointly | F-test vs model with trend + weekend + hour only | Reject — seasonal variation exists |
| 2 | Semi-annual terms (sin2, cos2) = 0 jointly | Partial F-test vs annual-only model | Do not reject — drop sin2/cos2 |
| 3 | All 23 hour dummies = 0 jointly | F-test vs model without hour dummies | Reject — within-day shape highly significant |
| 4 | AIC/BIC model comparison | Full (annual + semi-annual) vs annual-only + hour | Annual-only preferred by BIC |
| 5 | Amplitude vs noise floor | √(b2²+b3²) and √(b4²+b5²) vs σ_resid | Semi-annual amplitude small relative to σ_resid |

**Decision on semi-annual terms:** Drop sin(4πτ) and cos(4πτ) despite sin2 being individually significant. Rationale: (a) cos2 not significant; (b) amplitude small relative to σ_resid; (c) likely reflects 2022–23 energy crisis asymmetry rather than a structural bi-annual pattern; (d) projecting a potentially spurious term over 25 years introduces instability. Annual-only model preferred by BIC; sin2 retained would be AIC-preferred, but AIC trades off less against overfitting.

**Terms also tested and dropped:** hour×season interactions (not significant once Fourier terms included); per-country OLS on GB and FR separately (replaced by direct spread OLS to eliminate Jensen's inequality bias).

**Final estimated specification:**
```
f_S(t, h) = b0 + b1·τ + b2·sin(2πτ) + b3·cos(2πτ) + b6·D_t + Σ_{h=0}^{22} b_h·H_{h,t}
```

**Projection (§13):** `tau` set to 0.0 in the feature matrix. f_S then demeaned year-by-year so its annual mean = 0 GBP/MWh. f_S carries only the within-year shape (Fourier harmonics, hour dummies, weekend dummy). Annex M spread level is the sole annual mean contributor in projection. OU process X_t mean-reverts to c_ou (≈ 0).

---

## 3. Jump Detection (§10)

Cartea & González-Pedraz two-pass filter. Applied to **daily-averaged** residuals: hourly OLS residuals aggregated via `resid_h.resample('D').mean()` before any filtering.

**Pass 1 — iterative spike filter (max 20 iterations):**
1. Compute first differences Δr_d = r_d − r_{d-1} on daily residuals.
2. Compute μ_Δ and σ_Δ on the current clean set. Flag dates where |Δr_d − μ_Δ| > 3σ_Δ.
3. Set flagged values to NaN; recompute μ_Δ, σ_Δ on remaining clean values. Repeat.
4. Converge when no new flags. Candidate jump dates = all dates flagged in any iteration.

**Pass 2 — OLS CI confirmation:**
- QR leverage scores from hourly feature matrix X: `h_ii = (Q²).sum(axis=1)` where Q from `np.linalg.qr(X)`.
- Hourly CI half-width: `ci = 1.96 × √(h_ii × MSE_OLS)`. Averaged to daily: `ci_half_daily = ci.resample('D').mean()`.
- Confirm **positive** jump only if r_d > +ci_half at that date.
- Confirm **negative** jump only if r_d < −ci_half at that date.
- Prevents false positives near high-leverage dates.

**Jump size (Cartea footnote 13):**
```
size_d = S̃_d − S̃_{d-1}     (first difference of daily residual at jump date)
```
Exception: if jump is the first observation (position = 0), use size = S̃_d (level). Classification as positive/negative by sign(Δr_d).

**Jump component Y_t** (Cartea Eq. 22):
```
Y_t = e^{−β·Δt} · Y_{t-1} + ΔJ⁺_t − ΔJ⁻_t
```
Positive and negative jumps estimated **separately** (each with own β and λ_q). Jump intensities λ_q = count_jumps_in_quarter / count_days_in_quarter (4 seasonal regimes). β estimated jointly with OU α in NLS (§4).

---

## 4. OU + Jump NLS Estimation (§11)

Joint NLS. For each candidate β_yr (jump decay rate, per year):

**Step 1 — reconstruct Y_t:**
```python
phi_Y = exp(-beta_yr / 365.25)
Y = np.zeros(n)
for (jp, js) in zip(jump_positions, jump_sizes):
    t_idx = np.arange(jp, n)
    Y[t_idx] += js * phi_Y ** (t_idx - jp)
```

**Step 2 — compute X_t = S̃_t − Y_t, fit AR(1) by OLS, return MSE.**

**Step 3 — NLS search:**
```python
scipy.optimize.minimize_scalar(objective, bounds=(1.0, 5000.0), method='bounded')
```
Only β_yr is searched. φ and σ_d derived analytically from AR(1) at each β.

**AR(1) model on X_t:**
```
X_t = c + φ·X_{t-1} + ε_t,    ε_t ~ N(0, σ_d²)
```

**Continuous-time mapping (Cartea Eqs. 20–21):**
```
φ      = e^{−α·Δt}                          (Δt = 1/365.25 yr for daily)
σ_d²   = σ²(1 − e^{−2α·Δt}) / (2α)         (derived from φ at optimal β)
c      = μ(1 − φ)                            (long-run mean μ ≈ 0 for spread)
α      = −ln(φ) × 365.25                     (mean-reversion speed, per year)
```

Half-life (days) = ln(2) / α × 365.25. Correlation between OU innovations and jump process: zero by construction (jump-cleaned residuals used for OU fitting).

---

## 5. Monte Carlo Simulation (§15)

Daily Euler scheme. RNG: `np.random.default_rng(RANDOM_SEED)` (modern NumPy API). N_PATHS = 10,000, N_PROJ_YEARS = 20, BATCH = 500 paths per loop (memory management):

```python
rng = np.random.default_rng(RANDOM_SEED)
for b0 in range(0, N_PATHS, BATCH):
    X = np.zeros(BATCH)
    for d in range(n_days):
        q = proj_dates[d].quarter
        X = c_ou + phi * X + sigma_d * rng.standard_normal(BATCH)
        # Bidirectional jumps — positive and negative estimated separately:
        for jp, sign in [(jp_pos, +1.0), (jp_neg, -1.0)]:
            lam = jp['lam_by_q'][q]
            if lam > 0:
                X += sign * (rng.random(BATCH) < lam) * rng.exponential(jp['beta'], BATCH)
        S_h = f_s_shape[d, :] + spread_level[d] + X[:, np.newaxis]   # (BATCH, 24)
        rev_d = np.abs(S_h).sum(axis=1) * CAPACITY_MW * AVAILABILITY / 1e6 * capture_ratio
        annual_rev[yr_idx] += rev_d
```

- `f_s_shape[d, h]`: f_S shape with τ=0, demeaned (mean-zero annual shape); shape (n_days, 24)
- `spread_level[d]`: absolute annual spread level from Annex M (2016/17-RPI-real GBP/MWh); see §7
- `jp['beta']`: exponential scale for jump sizes (output of NLS); `lam_by_q[q]`: arrival rate per day in quarter q
- Same `rng` instance shared across all three scenarios — differences are purely from `spread_level`, not random variation
- `annual_rev` stored in 2016/17-RPI-real £m

---

## 6. Capture Ratio (§12)

Rolling out-of-sample back-test over available actual years (currently 2024–2025):
```
CR_yr = audited_turnover[yr] / simulated_gross_P50[yr]
CAPTURE_RATIO = mean(CR_yr over test years)
```

Back-test uses **Oct 2022 Annex M** vintage (the only vintage predating both test-year training cutoffs). That vintage is in 2022-GDP-real; rebased to 2016/17-RPI-real using hardcoded GDP growth rates:
```python
_GDP_FROM_2022 = {2023: 0.069000, 2024: 0.040225, 2025: 0.031785, 2026: 0.016721}
```

Post-Brexit, IFA2 sells capacity in explicit forward auctions (T-1 day and longer). Auction clearing price < realised spot spread; traders capture the residual. CR also absorbs TSO charges, balancing costs, and outages. Single ratio preferred over hourly censoring — capacity is committed day-ahead; no hourly decision right exists.

---

## 7. Three-Scenario Structure (§14)

| Scenario | GB path | FR path |
|----------|---------|---------|
| Reference | Annex M Feb 2026 — Reference sheet, "baseload" row | FR Central nodes |
| FFP_Low | Annex M Feb 2026 — FFP_Low sheet | FR Low Surplus nodes |
| FFP_High | Annex M Feb 2026 — FFP_High sheet | FR High CO₂/Gas nodes |

**Critical: Annex M is in 2024-GDP-real, not 2016/17-RPI-real.**

Annex M note 15: prices use the GDP deflator. Cap/floor is set in 2016/17-RPI-real. Apply `adj_t` to every projected price (both GB and FR) before use:

```
adj_t = GDP_cum_t × RPI_1617 / RPI_t

  GDP_cum_t = ∏(1 + GDP_deflator[y])  for y = 2025 .. t
```

- `GDP_deflator[y]`: read from Annex M Reference sheet **row index 6** (0-based), column aligned with year row (row index 2).
- `RPI_t`, `RPI_1617 = 264.992`: from `FPA_RPI` table in `data.md §6`.
- Pre-compute: `ADJ_FACTORS = {yr: adj_t(yr) for yr in 2020..2050}`.

**GB scaling:** Corrects methodology basis gap (N2EX day-ahead vs Annex M baseload):
```
gb_scale = mean( panel_actual_GB[yr] / annex_m_ref_raw[yr]  for yr in 2023–2025 )
gb_proj[yr] = gb_ref[yr] × gb_scale × adj_t[yr]               (2016/17-RPI-real GBP/MWh)
```
`panel_actual_GB` values are 2016/17-RPI-real (deflated from nominal). 2022 excluded — Annex M embeds actual 2022 prices so ratio ≈ 1.0 (no signal).

**FR interpolation:** Node values (EUR/MWh; see `data.md §2`) linearly interpolated between node years; multiplied by 2024–25 panel mean FX rate (`fx_eur_gbp_fwd = panel.loc['2024':'2025','fx_eur_gbp'].mean()`); then × adj_t. Extrapolated flat beyond 2040.

**Annual spread level — added as absolute mean contribution to MC:**
```
spread_level[yr] = (gb_ref[yr] × gb_scale  −  fr_proj_eur[yr] × fx_fwd) × adj_t[yr]
```
This is the **absolute** projected annual mean spread in 2016/17-RPI-real GBP/MWh — **not a delta from an anchor**. In the MC: `S[d,h] = f_s_shape[d,h] + spread_level[d] + X[d]`. f_S is demeaned to zero annual mean; OU mean-reverts to c_ou ≈ 0; so `spread_level` is the sole annual mean contributor.

---

## 8. Price Basis Conversions

**RPIt** (2016/17-real → nominal): read from `Indexation` sheet of W1 CFFM2 Excel (row 11).
Conversion: `rev_nominal = rev_1617_real × RPIt`

**CPIHt** (2024-CPIH-real index): `CPIHt = CPIH_level[yr] / 132.9`
Historical values in `CPIH_HIST`; projected at `CPIH_GROWTH = 0.025` pa from 2024.

**Cross-conversion** (2016/17-real → 2024-CPIH-real):
```
rev_cpih = rev_1617_real × RPIt / CPIHt
```

**W3 revenue input:** assessed revenues written to W3 Excel in 2024-CPIH-real (not nominal).
CPIHt values also written to W3 Inputs row 145 for model consistency.

---

## 9. Cap/Floor Breach Calculation

**Assessment periods (Ofgem CFFM2 calendar-year approximation):**

| Period | Calendar years | Status |
|--------|---------------|--------|
| P1 | 2020–2024 | Closed; actual ICFap = £245.2m |
| P2 | 2025–2029 | Open |
| P3 | 2030–2034 | Open |
| P4 | 2035–2039 | Open |
| P5 | 2040–2044 | Open |

Op year N → calendar year = 2020 + N. ODR = 0.03945 real (from CFFM2 Assessment sheet row 13; also hardcoded in §19).

**Annual breach:** For each projection year yr and each MC path p:
```
P(rev > cap)[yr]   = mean( annual_rev[p,yr] > CLt_real[yr]  for p in paths )
P(rev < floor)[yr] = mean( annual_rev[p,yr] < FLt_real[yr]  for p in paths )
```

**5-year NPV breach** (Ofgem assessment periods P2–P5):
```
NPV_rev[p] = Σ_{yr in period} annual_rev[p,yr] / (1+ODR)^(yr − period_start)
P(NPV > NPV_cap) = mean( NPV_rev[p] > Σ CLt_real[yr] × disc_factor[yr] )
```

CLt and FLt read from `Revenue Adjustment` rows 11–12 (nominal), deflated by RPIt to get 2016/17-real. Revenue matrix includes ACTUALS (nominal → real via RPIt) for 2022–2025; 2021 set to 0 (not disclosed).

W3 cap and floor are constant in 2024-CPIH-real; compared directly after converting MC revenues via rev_cpih formula above.

---

## 10. Equity Returns (§22)

Translates MC revenue paths into annual cash returns to the equity investor under both regulatory regimes. All W1 values in 2016/17-RPI-real £m; W3 in 2024-CPIH-real £m.

**Investment base:** Opening operational RAV year 1 from `IFA2CFFM1_PCR_decision.xlsm` Op RAV sheet. Includes IDC (interest during construction) capitalised over 2016–2021 construction period. W3 investment base approximated as W1_RAV × RPIt / CPIHt (W3 Op RAV sheet absent from W3 model).

**Annual P&L per regime year:**
```
EBIT    = Rev_eff − OPEX − Dep
NI      = EBIT × (1 − TAX)     if EBIT ≥ 0
        = EBIT                  if EBIT < 0   (no tax shield on losses)
FCFE    = NI + Dep − RplCap
Yld%    = FCFE / Opening_RAV_yr1 × 100
```

| Variable | Source | Notes |
|----------|--------|-------|
| Rev_eff | MC distribution, clipped to [floor, cap] for regulated; raw for uncapped | In regime's own real basis |
| OPEX | W1: `Allowances Cap` sheet (controllable + non-controllable); W3: `Inputs` rows 35–36 | Hardcoded 25-value arrays in §22 |
| Dep | W1: `Allowances Cap` sheet (RAV depreciation); W3: W1_Dep × RPIt / CPIHt | Straight-line over regime |
| RplCap | W1: `Op RAV` sheet replacement capex schedule; W3: W1_RplCap × RPIt / CPIHt | Lumpy; non-zero in specific years only |
| TAX | 25% (current UK corporation tax rate) | W1 model uses 19% — §22 overrides to 25% |

**Two revenue columns per regime (four columns total):**
- *Uncapped* — raw MC revenue, no regulatory clipping; shows market value
- *Regulated* — clipped to [floor, cap]; shows what IFA2 actually receives under the regime

**IRR calculation:**
```
cashflows = [−Opening_RAV_yr1, FCFE_yr1, FCFE_yr2, ..., FCFE_yr25]
IRR = r  such that  NPV(cashflows, r) = 0
```
Computed separately for FCFE and NI, and for uncapped vs regulated, per scenario (P10/P50/P90). Uses `numpy_financial.irr` with bisection fallback.

**Yield %** (annual, not IRR) shows cash returned per £ invested each year — useful for investors assessing annual distributable cash rather than terminal-value IRR.
