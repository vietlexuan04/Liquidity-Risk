# Liquidity Risk Analytics Toolkit

**English** | [Tiếng Việt](README_vi.md)

A simulation of a bank liquidity-risk analysis workflow under Basel III (LCR, NSFR) plus
stress testing, built on public FDIC Call Report data for **JPMorgan Chase Bank, N.A.**
(FDIC Cert #628), 2023Q1–2026Q2 (14 quarters). The goal is to demonstrate the workflow
(data pipeline → reconciled mapping → ratio engine → sensitivity / benchmark → stress
testing → SQLite for SQL / Power BI), not to reproduce JPMorgan's official internal figures.

**Units**: every amount in the raw data and in the CSV files is in **USD thousands** (the FDIC
unit). Tables in the README files are converted to USD billions ($B).

**Read this before using any number in this repo**: all LCR/NSFR figures are **proxies**
built from the public Call Report, which is not detailed enough for an exact regulatory
calculation. The proxy LCR sits **11.5–33.0 percentage points below** the LCR that JPMorgan Chase
Bank, N.A. discloses (all 14 quarters benchmarked, average gap −22.6pp). This is a known,
documented property of the model, not a bug.

## Pipeline (run in this order)

```
data/raw/jpm_628_raw.csv                 (downloaded manually from FDIC BankFind)
        │
src/parse_fdic_raw.py      ──→  data/processed/jpm_628_wide.csv, jpm_628_long.csv, mnemonic_labels.csv
        │                        (flattens FDIC's quarter-block export → one row per quarter)
src/build_mapping.py       ──→  mapping/liquidity_mapping.csv, nhnn_ratio_reference.csv
        │                        (assigns every balance-sheet line an LCR/NSFR role per Basel III
        │                         BCBS 238/295, with Vietnamese SBV (NHNN) thresholds for reference;
        │                         RECONCILES to ASSET / LIABEQ with zero difference, 14/14 quarters)
src/mapping_to_long.py     ──→  mapping/liquidity_mapping_long.csv
        │                        (derived long/tidy version for SQL / Power BI)
src/ratios.py              ──→  data/processed/ratios_by_quarter.csv
        │                        (HQLA by level with Basel Level 2 caps, LCR, ASF/RSF, NSFR, LDR)
src/sensitivity.py         ──→  data/processed/sensitivity_results.csv
        │                        (one-at-a-time tests on 17/18 Low-confidence lines,
        │                         theoretical ceilings, omission tests, combined envelope)
src/benchmark.py           ──→  data/processed/lcr_benchmark.csv
        │                        (proxy LCR vs disclosed LCR, 14 quarters; the disclosed
        │                         figures are MANUAL INPUT from the 10-Q filings)
src/stress_testing.py      ──→  data/processed/stress_*.csv
        │                        (3 fixed scenarios x 14 quarters, Monte Carlo deposit run-off,
        │                         survival horizon, reverse stress test — LCR only)
src/db.py                  ──→  liquidity_risk.db
                                 (loads all 12 CSV tables into one SQLite file)
```

`src/lcr_engine.py` holds the shared formulas used by `ratios.py`, `sensitivity.py` and
`stress_testing.py`, so the three scripts cannot drift apart.

Requirements: Python 3.8+ standard library only (no packages to install). Run everything from
the repo root:

```bash
for f in src/parse_fdic_raw.py src/build_mapping.py src/mapping_to_long.py src/ratios.py \
         src/sensitivity.py src/benchmark.py src/stress_testing.py src/db.py; do python3 "$f"; done
```

The run is deterministic (Monte Carlo uses a fixed seed), so it reproduces every CSV in the repo.

## Repository layout

```
data/raw/                  Original FDIC Call Report export (see "Getting the raw data")
data/processed/            All intermediate outputs and results (CSV)
mapping/                   LCR/NSFR mapping tables + methodology notes (mapping_README.md)
src/                       Python code, one script per pipeline step + shared engine
liquidity_risk.db          SQLite database with every output table, for SQL / Power BI
README.md                  This file (README_vi.md: Vietnamese version)
STRESS_TESTING_README.md   Full stress-testing methodology and results
```

No Power BI report file is included; `liquidity_risk.db` is the ready-made data source for one
(Power BI connects to SQLite through an ODBC driver).

## Getting the raw data

`data/raw/jpm_628_raw.csv` is the **"Assets, Liabilities, and Capital"** report for Cert #628,
USD thousands, 14 quarters from 31/03/2023 to 30/06/2026, exported as CSV from the
**"Customize a Report"** tool of FDIC BankFind (banks.data.fdic.gov/bankfind-suite/financialreporting).
`parse_fdic_raw.py` is written for exactly this layout (each quarter is a 3-column block:
mnemonic, value, spacer), so **the pipeline can only be reproduced with the same report type
and layout**.

The API URL below returns only 8 headline fields in a **different format** (one row per quarter)
and **cannot be fed to `parse_fdic_raw.py`**. It is kept as a quick reference for headline totals:

```
https://banks.data.fdic.gov/api/financials?filters=CERT:628 AND REPDTE:[20230101 TO 20261231]&fields=REPDTE,ASSET,DEP,DEPDOM,LNLSNET,SC,EQ,CHBAL&sort_by=REPDTE&sort_order=DESC&limit=100&format=csv&download=true
```

## Key findings

### 1. LCR / NSFR trend (baseline, 14 quarters)
LCR: 113% (2023Q1) → 85% (2026Q2); NSFR: 137% → 113%. Both decline over the period; LDR
rises from 45% to about 54%. Level 2 assets are only 9.8–13.1% of HQLA, so the Basel Level 2 caps
(40% / 15%) never bind.

### 2. Sensitivity and benchmark (validating the baseline before stressing it)
- The proxy is **11.5–33.0pp below** the disclosed bank LCR in every quarter (average −22.6pp),
  but it tracks the direction reasonably well: correlation of levels 0.79, and the two
  series move the same way in 8 of 11 quarter-on-quarter changes where the disclosed LCR moved.
- Within realistic Basel bounds, the most influential single assumptions are deposit and
  commitment outflow rates (`D_FO_IPC` −23.9pp, `O_OTHER` −19.4pp, `B_REPO` −17.7pp), the
  treatment of balances at foreign banks (`A_CASH_FOREIGN` −21.7pp) and loan inflows
  (`L_NBFI_SHORT` +16.3pp, `L_OTH_LE12` +10.8pp).
- **No single assumption explains the gap.** It is the sum of several conservative choices
  plus method differences that cannot be separated with public data: quarterly average vs
  quarter-end balances, US rule (12 CFR 249) vs Basel factors, and data granularity.

Details: `mapping/mapping_README.md`, section "Sensitivity and benchmark".

### 3. Errors found in review, fixed and documented
`CHCOIN` double-counted inside `CHBAL` (verified in 14/14 quarters, root cause traced to the
Call Report schedule definition); the loan maturity ladder was netted against net instead of
gross loans, producing a meaningless negative residual; and the NSFR initially omitted the 5% RSF
that Basel requires on undrawn committed credit and liquidity facilities (adding it lowers NSFR
by 2–3pp in every quarter). All are fixed and the reconciliation still matches exactly. Details:
`mapping/mapping_README.md`, "Issues found in review and how they were fixed".

### 4. Stress testing (LCR only; full results in `STRESS_TESTING_README.md`)
The combined scenario takes 2026Q2 LCR from 85.0% to 51.0% (−34.0pp). The idiosyncratic shock
(−31.2pp) is far heavier than the market-wide shock (−6.0pp) because deposit run-off and
commitment drawdowns are much larger dollar amounts than the extra haircuts on GSE / municipal
securities. With a front-loaded outflow profile, HQLA lasts 23.8 days at baseline and 9.6 days
under the combined scenario.

## Known limitations (read before using any number)

- LCR inflows are mostly not modelled (0% except `L_NBFI_SHORT`) → proxy is too low.
- Trading liabilities (`B_TRADEL`) have no LCR outflow → proxy is too high on this point
  (−2.5 to −11.1pp if 20–100% outflow were applied).
- Pledged securities (`SCPLEDGE`, $78.2B at 2026Q2) are kept in HQLA; deducting them in full
  would lower LCR by 7.0pp (see the omission test).
- Uniform-maturity assumption for aggregated ≤1-year lines.
- No management action / counterbalancing capacity in stress testing.
- 18 of 48 mapping lines are `confidence=Low`; their impact is quantified by sensitivity tests,
  not just flagged.
- Mapping factors follow Basel (BCBS 238/295), while the disclosed LCR follows the US rule and is
  a **quarterly average**; the proxy uses **quarter-end** balances.
- Data is the bank-level (solo) Call Report, not consolidated JPMorgan Chase & Co.
- **NSFR has no benchmark** (no comparable disclosure is used), so the NSFR proxy is unvalidated.
  The NSFR proxy also has no RSF for derivative liabilities and assumes 0% RSF on unconditionally
  cancellable card lines and on guarantees / letters of credit (Basel leaves these to national discretion).
- Disclosed LCR figures in the benchmark are **manual input** (14 quarters), not generated by code.
- Stress factors are **illustrative assumptions**, not calibrated to a supervisory scenario or a
  historical crisis; stress does not change inflows and does not model fire-sale losses.
- Monte Carlo samples the 4 deposit lines **independently** (correlation 0); the 20% relative
  standard deviation is a chosen parameter. Monte Carlo, survival horizon and reverse stress run
  for 2026Q2 only.
- Mapping formulas are evaluated with `eval()` (builtins disabled) — fine for the CSV maintained
  in this repo, **not safe for untrusted CSV input**. No automated tests yet.

Full list with line-by-line rationale: `mapping/mapping_README.md` and the `rationale` column of
`mapping/liquidity_mapping.csv`.
