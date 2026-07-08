# Methodology — IFA2 Spread-Direct OU Model

Primary reference: Abadie & Chamorro (2021), *Energy* 233, 121177.
Jump structure: Cartea & González-Pedraz (2012), *Energy Economics* 34.

---

## 1. Spread Decomposition

```
S_t = f_S(t, h) + X_t
```

- **S_t** — hourly GB−FR spread (GBP/MWh); constructed as `GB_price − FR_price_EUR × fx_eur_gbp`
- **f_S(t, h)** — deterministic seasonal + trend component, estimated by OLS on hourly data
- **X_t** — stochastic daily OU residual (jump-cleaned)

Revenue per day:
```
rev_d = Σ_{h=1}^{24} |S_{d,h}| × CAPACITY_MW × AVAILABILITY / 1e6 × CAPTURE_RATIO  (£m)
```

---

## 2. Deterministic Component f_S(t, h)

OLS on all hourly observations (§6–9):

```
f_S(t, h) = b0 + b1·τ + b2·sin(2πt) + b3·cos(2πt) + b4·D_t + Σ_{h=1}^{23} b_h·H_{h,t}
```

| Term | Description |
|------|-------------|
| τ | Years since `t0_spread` (first hourly obs); frozen at ANCHOR_DATE in projection |
| sin(2πt), cos(2πt) | Annual Fourier harmonics (t in years) |
| D_t | Weekend + public holiday dummy (1 = GB or FR non-working day) |
| H_{h,t} | 23 hourly dummies (h=1..23); H24 implied as −sum of all others |

**Excluded terms (tested, dropped):**
- Semi-annual harmonics sin(4πt), cos(4πt): cos₂ not significant at 5%; combined R² gain < 0.001
- Hour×season interactions: not significant after Fourier terms included
- Per-country OLS (GB and FR separately): replaced by direct spread OLS to avoid Jensen's bias

**Projection:** τ frozen at `ANCHOR_DATE = 2025-01-01`. `PROJ_TAU_GROWTH = 0.0` (no trend
extrapolation). All 24-hour dummies and Fourier terms propagate forward unchanged.

---

## 3. Jump Detection (§10)

Cartea & González-Pedraz two-pass filter on **daily-averaged** OLS residuals (not hourly):

**Pass 1 — spike filter:**
1. Compute first differences Δr_d = r_d − r_{d-1} on daily residuals
2. Flag days where |Δr_d| > 3σ(Δr) and |Δr_{d+1}| > 3σ(Δr) (spike-and-revert pattern)
3. Remove flagged days; iterate until convergence

**Pass 2 — OLS CI confirmation:**
- Compute 95% CI half-width for f̂_S via QR leverage scores: `ci_half = z_{0.975} × σ_OLS × √h_ii`
- Confirm jump only if |r_d| > ci_half at that date (prevents false positives near high-leverage dates)

**Jump component Y_t** (Cartea Eq. 22):
```
Y_t = e^{−β·Δt} · Y_{t-1} + ΔJ⁺_t − ΔJ⁻_t
```
Positive and negative jumps estimated separately. Jump sizes exponential(β). Intensities
λ estimated per quarter (4 seasonal regimes). β estimated jointly with OU α in NLS (§4).

---

## 4. OU + Jump NLS Estimation (§11)

Joint NLS on jump-cleaned daily residuals X̃_t = r_d − Y_d:

```
X_t = c + φ·X_{t-1} + ε_t,    ε_t ~ N(0, σ_d²)
```

Continuous-time mapping (Cartea Eqs. 20–21):
```
φ  = e^{−α·Δt}                         (Δt = 1/365 yr for daily)
σ_d² = σ²(1 − e^{−2α·Δt}) / (2α)
c  = μ(1 − φ)                           (long-run mean μ ≈ 0 for spread)
```

NLS objective: minimise sum of squared AR(1) residuals over (α, β) jointly, given that
Y_d depends on β. φ and σ_d follow analytically from α.

Half-life = ln(2) / α. Correlation between OU innovations and jump process: zero by
construction (jump-cleaned residuals used for OU).

---

## 5. Monte Carlo Simulation (§15)

Daily Euler scheme, N_PATHS = 10,000, N_PROJ_YEARS = 20, RANDOM_SEED = 42:

```python
X[0] = 0
for d in range(n_days):
    q = quarter(d)
    J = exponential(beta) if uniform() < lambda[q]/365 else 0   # positive jumps
    X[d] = c + phi*X[d-1] + sigma_d*randn() + J
    for h in range(24):
        S[d,h] = fs_frozen[d,h] + delta_annex_m[d] + X[d]
    rev[d] = sum(|S[d,h]|) * CAPACITY_MW * AVAILABILITY / 1e6 * CAPTURE_RATIO
annual_rev[yr] = sum(rev[d] for d in year yr)
```

- Batched: BATCH = 500 paths per loop to manage memory
- `fs_frozen[d,h]`: f_S shape evaluated with τ = τ_anchor for all projection dates
- `delta_annex_m[d]`: annual spread-level shift (interpolated from `adj_df`; zero for Reference in base year)
- Same RNG seed across all three scenarios — differences between scenarios are purely from δ, not noise
- `annual_rev` stored in 2016/17-RPI-real £m

---

## 6. Capture Ratio (§12)

Rolling out-of-sample back-test over available actual years (currently 2024–2025):

```
CR_yr = audited_turnover[yr] / simulated_gross_P50[yr]
CAPTURE_RATIO = mean(CR_yr over test years)
```

**Economic rationale:** Post-Brexit, IFA2 sells interconnector capacity in explicit forward
auctions (T-1 day and longer). Auction clearing price < realised spot spread; traders
capture the residual. CR also absorbs TSO charges, balancing costs, and force majeure outages.
A single stable ratio is preferred over hourly censoring because there is no hourly decision
right — capacity is committed day-ahead and cannot be withheld hour-by-hour.

---

## 7. Three-Scenario Structure (§14)

| Scenario | GB path | FR path |
|----------|---------|---------|
| Reference | Annex M Feb 2026 — Reference sheet, "baseload" row | FR Central nodes |
| FFP_Low | Annex M Feb 2026 — FFP_Low sheet | FR Low Surplus nodes |
| FFP_High | Annex M Feb 2026 — FFP_High sheet | FR High CO₂/Gas nodes |

**GB scaling:** Annex M is in p/kWh real 2024 baseload. Scale factor corrects the
methodology basis gap vs N2EX day-ahead prices:
```
gb_scale = mean( panel_actual_GB[yr] / annex_m_reference[yr]  for yr in 2023–2025 )
```
2022 excluded (Annex M embeds actual 2022 prices, ratio ≈ 1.0 — no information).
Scaled GB projection: `gb_proj[yr] = gb_scale × annex_m[yr]`.

**FR interpolation:** Node values (EUR/MWh real 2025) linearly interpolated between
published years; converted to GBP at 2024–25 panel average FX rate.

**Spread delta:** `δ[yr] = (gb_proj[yr] − fr_proj_gbp[yr]) − (gb_proj[anchor] − fr_proj_gbp[anchor])`
Applied as a uniform daily shift to all hours in year yr.

---

## 8. Price Basis Conversions

**RPIt** (2016/17-real → nominal): read from `Indexation` sheet of W1 CFFM2 Excel.
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

**Annual breach:** For each projection year yr and each MC path p:
```
P(rev > cap)[yr]   = mean( annual_rev[p,yr] > CLt_real[yr]  for p in paths )
P(rev < floor)[yr] = mean( annual_rev[p,yr] < FLt_real[yr]  for p in paths )
```

**5-year NPV breach** (Ofgem assessment periods P2–P5):
```
NPV_rev[p] = Σ_{yr in period} annual_rev[p,yr] / (1+ODR)^(yr - period_start)
P(NPV > NPV_cap) = mean( NPV_rev[p] > Σ CLt_real[yr] × disc_factor[yr] )
```
CLt and FLt read from `Revenue Adjustment` rows 11–12 (nominal), deflated by RPIt.
W3 cap and floor are constant in 2024-CPIH-real; compared directly after converting MC revenues.
