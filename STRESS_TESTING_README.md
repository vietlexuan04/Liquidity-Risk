# Stress testing — methodology and results

**English** | [Tiếng Việt](STRESS_TESTING_README_vi.md)

Applies `src/stress_testing.py` to the validated baseline (see `mapping/mapping_README.md`,
"Sensitivity and benchmark"). **LCR only** — NSFR is not stressed in this version. All figures
are in `data/processed/stress_*.csv`, or in `liquidity_risk.db` (tables `stress_*`).

Raw data is in USD thousands; the tables below are converted to USD billions ($B).

## Key explicit assumptions

**No management action / counterbalancing capacity.** The model does not assume the bank sells
non-HQLA assets, draws contingency funding lines or cuts new lending in response to the shock.
Results are the purely mechanical response of the reported balance sheet, so they are
**deliberately more pessimistic** than what a real bank would experience.

**The proxy baseline is already 11.5–33.0pp below the LCR JPMorgan discloses** (see benchmark).
Every result is therefore shown both as an absolute LCR and as a **delta vs the model's own
baseline**. Reading the absolute number alone suggests a bank in distress; that is a property
of the conservative proxy, not a real weakness of JPMorgan.

**Factors are clamped to [0%, 100%].** A run-off rate or haircut above 100% has no economic
meaning, so every stressed factor is capped (this matters for the reverse stress test).

## 1. Three fixed scenarios

| | Idiosyncratic | Market-wide | Combined |
|---|---|---|---|
| Insured non-brokered deposits (`D_INS_STABLE`) | 5% → 10% | unchanged | 10% |
| Insured brokered deposits (`D_INS_BRO`) | 10% → 25% | unchanged | 25% |
| Uninsured corporate / foreign-office deposits (`D_DOM_UNINS_OTH` / `D_FO_IPC`) | 40% → 70% | unchanged | 70% |
| Undrawn commitments (`O_*`) | drawdown x1.5 | unchanged | x1.5 |
| HQLA haircut GSE / muni (`S_GSE` / `S_MUNI`) | unchanged | 15% → 25% / 50% → 65% | 25% / 65% |
| Repo funding (`B_REPO`) | unchanged | 25% → 50% | 50% |

`B_ST` (other borrowings / FHLB advances ≤1y) is **not stressed**: the baseline already assumes
100% non-rollover of the share that matures within 30 days, which is the Basel maximum for
maturing unsecured wholesale funding. The rest is not contractually due inside the 30-day
window, so stressing it would mean changing the maturity assumption, not the run-off rate.

**About the shock sizes**: they are **illustrative assumptions**, not calibrated to a specific
supervisory scenario (Fed, Basel) or to data from a past crisis. Use the results to compare the
relative sensitivity of risk groups, not as a forecast of the LCR in a real crisis.

**Results (LCR %, 2026Q2; all 14 quarters in `stress_scenarios_by_quarter.csv`):**

| Scenario | LCR | Δ vs baseline (pp) | Δ vs baseline (%) |
|---|---:|---:|---:|
| Baseline (no stress) | 85.0% | — | — |
| Idiosyncratic | 53.8% | −31.2 | −36.7% |
| Market-wide | 79.0% | −6.0 | −7.1% |
| Combined | 51.0% | −34.0 | −40.0% |

**Reading**: the idiosyncratic shock is far heavier than the market-wide shock (−31pp vs −6pp)
because deposit run-off and commitment drawdowns are much larger dollar amounts than the extra
haircuts on GSE / municipal securities. Those securities are a small part of the $957B HQLA:
Level 1 assets make up $838B (mainly $483B of US Treasuries and $244B of balances at foreign
banks, assumed to be foreign central-bank reserves) and keep a 0% haircut. The pattern holds in
**all 14 quarters** (idiosyncratic −31 to −44pp, market-wide −4 to −7pp, combined −34 to −46pp).

## 2. Monte Carlo deposit run-off (2026Q2, 10,000 draws)

The run-off rates of the 4 deposit lines (`D_INS_STABLE`, `D_INS_BRO`, `D_DOM_UNINS_OTH`,
`D_FO_IPC`) are drawn from Beta distributions centred on the combined-scenario values
(std = 20% of the mean). All other parameters (haircuts, drawdowns, repo) are **held at their
combined-scenario values**; they are not randomised together because there is no basis for
choosing correlations between different risk types.

Two modelling choices drive the tails: (1) the 4 deposit lines are drawn **independently**
(correlation 0), so the tails are probably too thin — in a crisis, deposit types tend to run
together; (2) the 20% relative standard deviation is **a chosen parameter**, not calibrated.

| Percentile | LCR | Δ vs baseline (pp) |
|---|---:|---:|
| p5 | 44.5% | −40.5 |
| p25 | 47.7% | −37.4 |
| p50 | 50.7% | −34.4 |
| p75 | 54.5% | −30.5 |
| p95 | 61.7% | −23.3 |

**Cross-check**: the median (50.7%) is close to the combined point scenario (51.0%), as expected
when the distribution is centred on the same factors. It is slightly lower because the Beta
distributions for the two 70% run-off lines are left-skewed (their median run-off is a little
above 70%), and those two lines dominate the outflow.

## 3. Survival horizon (2026Q2)

Days until cumulative net outflows exhaust HQLA (HQLA assumed usable from day 1), under two
outflow profiles for the same 30-day net outflow:

- **Uniform** (`net_outflow / 30` per day). Note this is just **30 × LCR** — it adds no
  information beyond the LCR and is shown only as a reference.
- **Front-loaded** (illustrative): 40% of the 30-day outflow in days 1–5 (8% per day), the
  remaining 60% over days 6–30 (2.4% per day), reflecting that run-offs concentrate early in a
  real stress. This is the informative column.

| Scenario | HQLA | 30-day net outflow | LCR | Days (uniform) | Days (front-loaded) |
|---|---:|---:|---:|---:|---:|
| Baseline | $957.1B | $1,125.7B | 85.0% | 25.5 | 23.8 |
| Idiosyncratic | $957.1B | $1,779.3B | 53.8% | 16.1 | 10.7 |
| Market-wide | $940.6B | $1,190.5B | 79.0% | 23.7 | 21.3 |
| Combined | $940.6B | $1,844.1B | 51.0% | 15.3 | 9.6 |

Front-loading costs about 2 days at baseline but 5–6 days under the deposit-run scenarios: the
heavier the run, the more its timing matters. The baseline is already below 30 days because the
proxy baseline is below the disclosed LCR — not because JPMorgan would actually last only ~24 days.

## 4. Reverse stress test (2026Q2)

Shock intensity θ (θ = 0: baseline, θ = 1: exactly the combined scenario). Each factor is
interpolated linearly (extrapolated outside [0, 1]) and then **clamped to [0%, 100%]**:

| Target LCR | θ required | Interpretation |
|---|---:|---|
| 100% | **−0.23** | The baseline is already below 100%, so the stress would have to be **reduced below baseline** by 23% of the combined-scenario gap. This shows the conservatism of the proxy, not that JPMorgan is below the regulatory minimum. |
| 75% | 0.20 | 20% of the combined-scenario intensity is enough to reach 75%. |
| 50% | 1.05 | Slightly more (105%) than the combined scenario is needed to reach 50%. |
| Floor | — | With **every** stressed factor at 100% (all stressed deposits and commitments run off, repo funding fully lost, GSE / muni securities worthless), LCR bottoms out at **17.0%**. Lower values need shocks outside this scenario's levers (e.g. losses on Level 1 assets), so "HQLA fully depleted" is not reachable within this scenario family. |

## Limitations of the stress-testing module

- LCR only; NSFR is not stressed.
- Scenarios change only outflow rates and haircuts. **Inflows are not stressed**, and fire-sale
  losses on HQLA are not modelled.
- Sections 2 (Monte Carlo), 3 (survival horizon) and 4 (reverse stress) run for **2026Q2 only**.
- Reverse stress interpolates **linearly** in θ; the front-loaded survival profile is illustrative.
- No management action (see the assumptions above).

## How to query

All tables above are in `liquidity_risk.db` (SQLite): `stress_scenarios_by_quarter`,
`stress_montecarlo_2026q2`, `stress_survival_horizon`, `stress_reverse_test`. Join with
`ratios_by_quarter` on `report_period` (stored as TEXT, `YYYYMMDD`) to compare with the
baseline. Rebuild the DB at any time with `python3 src/db.py` (it reads the CSVs in
`data/processed/` and `mapping/`; never edit the `.db` file by hand).
