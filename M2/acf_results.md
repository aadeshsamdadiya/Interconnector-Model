# ACF Diagnostic Results — X_t (OU Residual)

**Script:** `acf_check.py`  **Plot:** `acf_xt_check.png`  **Run:** 2026-07-08

---

## Setup

X_t is the OU component after the full pipeline: OLS → Cartea jump filter → NLS joint estimation of OU mean-reversion (α) and jump decay (β). X_t = S̃_t − Y_t where S̃_t is the daily OLS residual and Y_t is the reconstructed jump component.

Data: `GB-FR07.xlsx` (Dec 2021 – Jul 2026), 2016/17-RPI-real deflated.

Two samples compared to test whether long memory is structural or crisis-driven:
- **Full**: Dec 2021 – Jul 2026 (1,672 days, 60 jumps, 3.6%)
- **Post-crisis**: Jan 2023 – Jul 2026 (1,284 days, 40 jumps, 3.1%)

Estimated parameters:

| Sample | φ | κ (yr) | Half-life |
|--------|---|--------|-----------|
| Full   | 0.7145 | 122.8 | 2.06 days |
| Post   | 0.7043 | 128.0 | 1.98 days |

---

## ACF Table (empirical vs AR(1) φ^k)

| Lag | Full ACF | Full φ^k | Post ACF | Post φ^k | Excess (full)? |
|-----|----------|----------|----------|----------|----------------|
| 1   | 0.7145   | 0.7145   | 0.7042   | 0.7043   |                |
| 2   | 0.5418   | 0.5105   | 0.5306   | 0.4961   |                |
| 3   | 0.4684   | 0.3648   | 0.4334   | 0.3494   | *              |
| 5   | 0.3969   | 0.1862   | 0.2988   | 0.1734   | *              |
| 7   | 0.3436   | 0.0951   | 0.2437   | 0.0860   | *              |
| 10  | 0.2641   | 0.0347   | 0.1940   | 0.0301   | *              |
| 15  | 0.2477   | 0.0065   | 0.1588   | 0.0052   | *              |
| 20  | 0.2011   | 0.0012   | 0.1444   | 0.0009   | *              |
| 30  | 0.1549   | ≈0       | 0.0468   | ≈0       | *              |
| 45  | 0.0876   | ≈0       | 0.0408   | ≈0       |                |
| 60  | 0.0269   | ≈0       | −0.0119  | ≈0       |                |

---

## Ljung-Box — X_t Levels

H0: no autocorrelation. All p = 0.000 → reject at every lag in both samples.

| Lag | Full stat | Full p | Post stat | Post p |
|-----|-----------|--------|-----------|--------|
| 5   | 2285.6    | 0.000  | 1531.2    | 0.000  |
| 10  | 3118.2    | 0.000  | 1859.0    | 0.000  |
| 20  | 4072.3    | 0.000  | 2201.6    | 0.000  |
| 30  | 4570.9    | 0.000  | 2259.1    | 0.000  |

---

## Ljung-Box — X_t² (Volatility Clustering)

H0: no volatility clustering. All p = 0.000 → GARCH effects present in both samples.

| Lag | Full stat | Full p | Post stat | Post p |
|-----|-----------|--------|-----------|--------|
| 5   | 983.4     | 0.000  | 317.3     | 0.000  |
| 10  | 1154.1    | 0.000  | 340.4     | 0.000  |
| 20  | 1345.8    | 0.000  | 472.0     | 0.000  |
| 30  | 1588.8    | 0.000  | 518.9     | 0.000  |

---

## Interpretation

**Excess memory**: AR(1) under-specifies the persistence of X_t. At lag 10, the empirical ACF (0.26 full, 0.19 post) is 7–6× the AR(1) prediction (0.035, 0.030). The decay is much slower than φ^k implies, persisting meaningfully out to lag 30.

**Crisis contribution**: Some long memory is crisis-driven — lag 30 drops from 0.155 (full) to 0.047 (post-crisis). But excess memory remains structural: even post-2023 the ACF at lag 10–20 is far above the AR(1) baseline.

**Volatility clustering**: X_t² is highly autocorrelated — GARCH(1,1) on innovations is warranted. Effect on valuation: GARCH fattens **both** tails without materially changing the mean (unconditional variance is unchanged; E[σ_t] ≤ σ_unconditional by Jensen on concave √). During high-volatility clusters revenues spike → higher cap breach probability; during quiet periods revenues compress → higher floor breach probability. GARCH does not simply inflate revenues — it adds dispersion in both directions.

**Valuation implication**: The model underestimates how long low-spread spells persist. Periods where the spread is suppressed (e.g. post-cannibalisation) will last longer in reality than the 2-day half-life implies, meaning **floor breach probabilities in P3–P5 are likely understated**.

## Options (to revisit)

1. **Re-estimate φ from longer-horizon ACF** — calibrate to empirical lag-20 ACF (~0.20) to imply HL ≈ 30 days. Simple drop-in change to `PHI` in config.
2. **AR(2) or ARMA(1,1)** — adds one parameter; captures intermediate decay without full regime-switching.
3. **2-state Markov switching on X_t mean** — structurally models persistent low/high spread regimes; more defensible but adds estimation complexity.
4. **Accept current model + note caveat** — current P3–P5 floor breach probabilities (38%, 100%, 100%) are already high; direction of bias doesn't change investment conclusion.
