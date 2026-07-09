# M1 Methodology: Bivariate OU Model for IFA2

**Reference:** Abadie & Chamorro (2021), "Valuation of Wind Energy Projects: A Real Options Approach"
*(adapted: bivariate mean-reverting jump-diffusion applied to electricity price spread)*

---

## 1. Price Basis

All prices in **2016/17-RPI-real GBP/MWh** before any estimation:

```
P_r(t) [real] = P_r(t) [nominal] × (RPI_1617 / RPI_year)
```

where `RPI_1617 = 264.992` (CHAW annual average, Jan 1987=100, FPA Input row 97).
EUR/MWh converted to GBP using daily-average EUR/GBP FX (Bloomberg).

---

## 2. Price Decomposition

Each regional price `r ∈ {GB, FR}` is decomposed as:

```
P_r(t) = θ_r + f_r(t) + X_r(t) + J_r(t)
```

| Component | Description |
|-----------|-------------|
| `θ_r` | Long-run mean (unconditional sample mean, full dataset) |
| `f_r(t)` | Deterministic seasonal component (Fourier, annual + semi-annual) |
| `X_r(t)` | OU mean-reverting residual |
| `J_r(t)` | Jump component (Poisson arrivals, exponential sizes) |

### 2.1 Seasonal Component

Annual and semi-annual Fourier harmonics fitted on demeaned daily prices:

```
f_r(t) = c1·sin(ωt) + c2·cos(ωt) + c3·sin(2ωt) + c4·cos(2ωt),   ω = 2π/365.25
```

Fitted by OLS on `P_r(t) − θ_r`.

### 2.2 Jump Detection

Days where `|z_r(t)| > 3σ_z` (after removing seasonal) are classified as jump events.
Jump union = GB jumps ∪ FR jumps; all union dates excluded from OU estimation.

### 2.3 OU Estimation (AR(1))

On the jump-cleaned residual `X_r(t) = P_r(t) − θ_r − f_r(t)` at non-jump dates:

```
X_r(t+1) = φ_r · X_r(t) + σ_r · ε_r(t)
```

Estimated by OLS: `φ_r = (X'Y)/(X'X)`,  `σ_r = std(Y − φ_r X)`.

Half-life: `HL_r = log(0.5) / log(φ_r)` days.

### 2.4 Correlation

Jump-cleaned OU innovations `{ε_GB, ε_FR}` are correlated:

```
ρ = corr(ε_GB, ε_FR)
```

Cholesky decomposition `L = chol([[1, ρ], [ρ, 1]])` used in simulation.

### 2.5 Jump Parameters

Separate Poisson–exponential model per region and direction:

```
λ_r^+ = n_pos / T_total    β_r^+ = mean(excess above +3σ threshold)
λ_r^- = n_neg / T_total    β_r^- = mean(excess below −3σ threshold)
```

---

## 3. Parameters (Full Sample, Dec 2021 – Jul 2026)

| Parameter | GB | FR |
|-----------|----|----|
| θ (2016/17-real £/MWh) | 104.35 | 80.97 |
| φ (daily AR) | 0.9209 | 0.9478 |
| σ_d (daily, £/MWh) | 21.40 | 20.09 |
| Half-life (days) | 8.4 | 12.9 |
| ρ (innovation corr.) | **0.5801** | — |
| Jump λ_pos (/day) | 0.0221 | 0.0221 |
| Jump β_pos (£/MWh) | 74.96 | 50.72 |
| Jump λ_neg (/day) | 0 | 0 |

Implied spread statistics: θ_spread = 23.39 £/MWh, σ_spread = 19.04 £/MWh.

> **Crisis-era note:** The 2022 energy crisis dominates the full sample. This inflates θ (crisis-era mean ≈ £23 spread vs post-crisis ≈ £8–10), σ, and φ (slow mean reversion from crisis persistence). No negative jumps appear because the crisis only pushed prices upward. The user chose to accept the full-sample parameters with no filtering — see M2 for the Annex M price-path approach.

---

## 4. Monte Carlo Simulation

Bivariate correlated OU with independent Poisson jumps, simulated daily over 20 years (2026–2045):

```
z(t) = L @ N(0, I_2)                                   # correlated innovations
X_GB(t+1) = φ_GB · X_GB(t) + σ_GB · z_0(t)
X_FR(t+1) = φ_FR · X_FR(t) + σ_FR · z_1(t)

# Independent Poisson jumps
X_GB += Poisson(λ_GB^+) · Exp(β_GB^+) − Poisson(λ_GB^-) · Exp(β_GB^-)
X_FR += Poisson(λ_FR^+) · Exp(β_FR^+) − Poisson(λ_FR^-) · Exp(β_FR^-)

S(t,d) = [θ_GB + f_GB(d) + X_GB] − [θ_FR + f_FR(d) + X_FR]
```

### 4.1 Diurnal Distribution

Each simulated daily spread `S(t,d)` is distributed across 24 hours using the empirical within-day shape:

```
S(t,d,h) = spread_shape[h] + S(t,d)
```

where `spread_shape[h]` is the full-sample mean hourly deviation from the daily average.

### 4.2 Revenue Formula

```
Rev(t, yr) = Σ_h |S(t,d,h)| × CAPACITY × AVAILABILITY × CR / 1e6   (GBPm/day)
```

Annual revenue = sum of daily revenues within each calendar year.
Units: **2016/17-RPI-real GBPm/yr** throughout.

---

## 5. Regulatory Assessment

### 5.1 Window 1 (RPI-indexed, 2016/17-RPI-real)

W1 cap/floor are constant in 2016/17-real because they are RPI-indexed:

```
W1_CAP_REAL  = £61.6m
W1_FLOOR_REAL = £37.8m
```

Annual breach: `P(Rev_yr > W1_CAP_REAL)` and `P(Rev_yr < W1_FLOOR_REAL)`.

5-year NPV assessment (ODR = 3.945% real, beginning-of-year discounting):

```
NPV_rev(P) = Σ_{k=0}^{4} Rev_{P,k} / (1 + ODR)^k
NPV_cap(P) = W1_CAP_REAL × Σ_{k=0}^{4} (1 + ODR)^{-k}  ≈ £285.5m per period
```

### 5.2 Window 3 (CPIH-indexed, 2024-CPIH-real)

Revenues converted before comparison:

```
Rev_CPIH(yr) = Rev_1617real(yr) × (RPI_yr / RPI_1617) / CPIH_yr
CPIH_yr = 1.025^(yr − 2024)   (OBR 2.5%/yr from ONS base 132.9 in 2024)
```

W3 thresholds are constant in 2024-CPIH-real:

```
W3_CAP_CPIH  = £79.885m   (PCL £71.04m + PCAC £3.99m)
W3_FLOOR_CPIH = £49.956m   (PFL £45.60m + PCAF £9.14m)
NPV_cap_W3   ≈ £370.2m per 5-year period
```

---

## 6. Key Results (10,000 paths, seed=42)

### Revenue (2016/17-RPI-real GBPm, stationary)

| Year | P10 | P50 | P90 |
|------|-----|-----|-----|
| 2026 | 102.9 | 129.7 | 163.7 |
| 2030 | 103.8 | 130.8 | 166.9 |
| 2035 | 103.6 | 130.6 | 166.3 |
| 2040 | 104.5 | 131.8 | 167.2 |
| 2045 | 103.5 | 131.0 | 166.4 |

Revenues stationary because theta is fixed at the full-sample mean (no trend).

### W1 NPV Assessment (2016/17-RPI-real)

| Period | Years | P50 NPV | Cap NPV | P > Cap | P < Floor |
|--------|-------|---------|---------|---------|-----------|
| P2 | 2026–2030 | £613.6m | £285.5m | **100%** | 0% |
| P3 | 2031–2035 | £615.8m | £285.5m | **100%** | 0% |
| P4 | 2036–2040 | £617.4m | £285.5m | **100%** | 0% |
| P5 | 2041–2045 | £613.6m | £285.5m | **100%** | 0% |

### W3 NPV Assessment (2024-CPIH-real)

| Period | Years | P50 NPV | W3 Cap NPV | P > Cap | P < Floor |
|--------|-------|---------|-----------|---------|-----------|
| P2 | 2026–2030 | £814.7m | £370.2m | **100%** | 0% |
| P3 | 2031–2035 | £847.4m | £370.2m | **100%** | 0% |
| P4 | 2036–2040 | £880.8m | £370.2m | **100%** | 0% |
| P5 | 2041–2045 | £907.5m | £370.2m | **100%** | 0% |

---

## 7. Comparison with M2

| Dimension | M1 (Bivariate OU, full sample) | M2 (Spread OU, Annex M) |
|-----------|-------------------------------|------------------------|
| Price model | Bivariate GB + FR, correlated | Single spread OU |
| Long-run mean | Full-sample historical (crisis-inflated) | Annex M / SP Global price path |
| Theta spread | £23.4 GBP/MWh | Declining per Annex M |
| OU half-life | 8.4d (GB), 12.9d (FR) | 2.1d (spread) |
| P50 revenue | ~£130m (stationary) | £65m → rising to £96m |
| Cap breach (W1) | 100% all periods | 65% (P2) → 100% (P3–P5) |
| Floor breach | 0% all periods | 0% all periods |
| Key assumption | Parameters set by historical data | SP Global FR price trajectory |
