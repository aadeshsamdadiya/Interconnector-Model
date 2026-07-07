# Methodology — Spread-Direct OU Model

## Decomposition

$$S_t = f_S(t, h) + X_t$$

- **S_t** — hourly GB–FR spread (GBP/MWh), constructed as GB_price − FR_price_GBP
- **f_S(t, h)** — deterministic component estimated by OLS
- **X_t** — stochastic daily mean-reverting residual

Revenue per hour = |S_{t,h}| × 1,000 MW × availability × capture_ratio / 1e6 (£m)

---

## Deterministic Component f_S(t, h)

OLS on all hourly spread observations:

$$f_S(t, h) = b_0 + b_1\tau + b_2\sin(2\pi t) + b_3\cos(2\pi t) + b_4 D_t + \sum_{h=1}^{23} b_h H_{h,t}$$

- **τ** — linear time trend (years since sample start); frozen at anchor in projection
- **sin/cos** — annual Fourier harmonics for seasonal spread pattern
- **D_t** — weekend + public holiday dummy (GB and FR calendars)
- **H_{h,t}** — 23 hourly dummies (H24 derived as negative sum); captures within-day shape

Semi-annual Fourier terms (sin₂, cos₂) dropped after significance testing — cos₂ not
significant at 5%; retaining sin₂ alone adds negligible R² and complicates interpretation.

---

## Jump Detection (Section 10)

Cartea & González-Pedraz (2012) iterative ±3σ filter applied to **daily-averaged** OLS
residuals. Hourly spikes average within a day, so jump detection on daily residuals avoids
false positives from within-day noise.

Two passes: (1) flag candidates where |Δresid| > 3σ of clean differences; (2) confirm
via OLS confidence interval (QR leverage scores) — a day is a confirmed jump only if the
residual level is outside the 95% f_S estimation CI. Prevents false positives near
high-leverage dates.

Positive and negative jump processes estimated separately (Cartea Eq. 22):
$$Y_t = e^{-\beta \Delta t} Y_{t-1} + \Delta J^+_t - \Delta J^-_t$$

---

## OU Estimation (Section 11)

Joint NLS estimation of OU mean-reversion (α) and jump decay (β) on jump-cleaned residuals
X̃_t = resid_s − Y_t. Daily AR(1) equivalent:

$$X_t = c + \phi X_{t-1} + \varepsilon_t, \quad \varepsilon_t \sim N(0, \sigma_d^2)$$

where φ = e^{−αΔt} and σ_d² = σ²(1 − e^{−2αΔt})/(2α) (Cartea Eq. 20–21).

Jump intensities λ estimated by quarter (4 seasonal regimes); jump sizes exponential(β).

---

## Monte Carlo Simulation (Section 15)

Daily Euler scheme, 10,000 paths × 20 projection years:

```
X_d = c + φ·X_{d-1} + σ_d·ε_d + J^+_d − J^-_d
S_{d,h} = f_S_frozen(d, h) + δ_Annex_M(d) + X_d
rev_d = Σ_h |S_{d,h}| × 1000 × avail / 1e6 × capture_ratio
```

- **f_S_frozen** — deterministic component with τ frozen at anchor (no trend drift)
- **δ_Annex_M(d)** — annual level shift from Annex M scenario (see [`data.md`](data.md))
- Same RNG seed across scenarios — scenario P50 differences are purely from δ, not noise

---

## Capture Ratio

Bridges gross spread revenue (model) to net assessed revenue (Ofgem accounts).

Estimated from rolling back-test (Section 12):
`capture_ratio = mean(audited_turnover[yr] / simulated_gross[yr])` over test years.

Economic rationale: IFA2 sells capacity in explicit forward auctions (post-Brexit).
Auction clearing price < realised spot spread. IFA2 receives the auction price; traders
capture the residual. Additional deductions: TSO charges, balancing costs, outage periods.

A single ratio is preferred over flow-based decomposition (Tobit / censored regression)
because the day-ahead market commits capacity one day ahead — there is no hourly
discretion to censor. The ratio is stable across test years and consistent with Section 18
waterfall analysis.

---

## Three-Scenario Structure (Section 14–15)

| Scenario | GB path | FR path | Narrative |
|----------|---------|---------|-----------|
| Reference | Annex M Reference (Feb 2026) | RTE BP 2025 Central | Gas moderates, renewables build |
| FFP_Low | Annex M FFP_Low | RTE Low surplus | Lower fossil fuel prices |
| FFP_High | Annex M FFP_High | RTE High CO₂/gas | Higher fossil fuel prices |

GB prices scaled by `gb_scale = panel_mean(2023–25) / annex_m_mean(2023–25)` to correct
the methodology basis gap between Annex M baseload (p/kWh real 2024) and N2EX day-ahead.

FR prices interpolated linearly between published RTE/ENTSO-E node years (EUR/MWh real
2025), converted to GBP at 2024–25 panel average FX rate.

The spread path is U-shaped in all scenarios: cannibalisation compresses spreads to
~2032–2035, then recovery as CO₂ and electrification costs rise in France.
