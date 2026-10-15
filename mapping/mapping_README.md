# mapping/ — Methodology notes

**English** | [Tiếng Việt](mapping_README_vi.md)

## What this folder is for

`liquidity_mapping.csv` assigns every line item in `data/processed/jpm_628_wide.csv`
(JPMorgan Chase Bank, N.A., FDIC Cert #628, 2023Q1–2026Q2) to a role in the Basel III LCR/NSFR
framework, with the factor (%) applied. `liquidity_mapping_long.csv` is a derived "long/tidy"
export (1 row = 1 line × 1 role in 1 ratio) for easier loading into SQL / Power BI.
**The wide file is the source of truth**; the long file is regenerated at any time by
`src/mapping_to_long.py` and should never be edited by hand.

**Important: these are illustrative proxy estimates, not JPMorgan's official LCR/NSFR.** The
public FDIC Call Report is not detailed enough for an exact regulatory calculation (no
day-by-day 30-day outflow schedule, no split of operational vs non-operational deposits as
Basel defines them, etc.). JPMorgan publishes its official LCR in its SEC filings — the numbers
in this repo **do not try to match it**; the aim is to show how the classification and
calculation work.

## Structure of `liquidity_mapping.csv` (wide, source of truth)

| Column | Meaning |
|---|---|
| `line_id` | Our own line code (not the FDIC mnemonic, because many lines are formulas) |
| `side` | `asset` / `liability` / `equity` / `offbs` (off-balance-sheet) / `memo` |
| `group` | Functional group: cash, securities, loans, deposits, borrowings, capital, commitments... |
| `definition` | Formula over the FDIC mnemonics in `jpm_628_wide.csv` |
| `hqla_level` / `hqla_haircut` | Only for HQLA-eligible lines (LCR numerator) |
| `lcr_outflow` / `lcr_inflow` | 30-day outflow / inflow rate (LCR denominator), only where relevant |
| `nsfr_asf` / `nsfr_rsf` | Available stable funding factor / required stable funding factor (NSFR) |
| `in_balance_sum` | 1 = included in the balance-sheet reconciliation; 0 = off-balance-sheet / memo |
| `confidence` | High / Medium / Low — confidence in the chosen factor (see below) |
| `rationale` / `source` | Reason for the factor, citing BCBS 238 (LCR) / BCBS 295 (NSFR) |

**Why many cells are empty**: a line only plays the roles it can play. A loan is never HQLA, so
the `hqla_*` columns are empty for `loans`. A deposit has no RSF (RSF is an asset-side measure),
so `nsfr_rsf` is empty for `deposits`. This is intentional, not missing data.

## How factors were chosen

- **HQLA level / haircut and LCR outflow / inflow**: Basel LCR (BCBS 238), cross-checked with the
  US rule, Reg WW (12 CFR 249), for the classification of GSE / GNMA securities, which the Basel
  text does not address in US terms.
- **ASF / RSF**: Basel NSFR (BCBS 295).
- **Vietnamese SBV (NHNN) thresholds** (LDR/CDR, short-term funding for medium/long-term loans,
  draft LCR/NSFR roadmap): see `nhnn_ratio_reference.csv`, citing Circular 22/2019/TT-NHNN,
  Circular 25/2026/TT-NHNN (raises the short-term-funding cap from 30% to 40%, effective
  1/7/2026) and the draft circular replacing Circular 22 (published 29/4/2026). Used **to compare
  thresholds only**, not in any formula.
- Where the Call Report is not granular enough for the Basel definition (e.g. operational vs
  non-operational deposits, municipal bond ratings), the **more conservative** of the two
  Basel-permitted factors is chosen, the line is marked `confidence=Low`, and the reason is
  written in `rationale`.

## Reconciliation — verified

The sum of all `side=asset` lines matches `ASSET` with **exactly zero difference**, and the sum
of all `side in (liability, equity)` lines matches `LIABEQ` with **exactly zero difference**, in
**all 14 quarters** (`src/build_mapping.py` prints this check on every run). This is the
necessary condition for trusting that the mapping covers 100% of the balance sheet with no
missing or double-counted lines.

## Issues found in review and how they were fixed

The issues below were found while reviewing the mapping and were verified on all 14 quarters
of data (or against the Basel text) before fixing — not fixed on a guess.

### 1. `CHCOIN` overlapping `CHBAL` (lines `A_CIPC` / `A_CASH_SCOPE_ADJ`)

Check: the identity `CHBAL = CHFRB + CHNUS + CHUS + CHCIC` holds **exactly in 14/14 quarters**.
Adding `CHCOIN` as a separate amount would make total assets **exceed** the reported `ASSET` in
every quarter, by exactly the value of `CHCOIN`. Conclusion: `CHCOIN` is not an additional asset;
its value is already inside one of the four components.

Root cause (confirmed): the four components follow FFIEC 031 Schedule RC-A, whose item 1 (MDRM
`RCFD0022`) is "Cash items in process of collection, unposted debits, **and currency and coin**"
— the sum of items `0020` (cash items) and `0080` (currency and coin). So `CHCIC` already contains
currency and coin, and `CHCOIN` ("Currency and Coin in Domestic Offices", `RCON0080`) is a
sub-item of it. Consistent with this, `CHCIC ≥ CHCOIN` in all 14 quarters.

Fix: two explicit lines — `A_CIPC` = `CHCIC` (full value, label as reported) and
`A_CASH_SCOPE_ADJ` = `-CHCOIN` (an explicit de-duplication line with a written reason) —
instead of hiding the subtraction inside `A_CIPC` as in the first version (`CHCIC - CHCOIN`:
right total, but the line name did not reflect the subtraction). Currency and coin itself is
counted once, as Level 1 HQLA, in `A_COIN`; the rest of `CHCIC` (items in collection plus
foreign-office currency) stays non-HQLA, which is slightly conservative. With the root cause
confirmed, `A_CASH_SCOPE_ADJ` is now `confidence=High`.

### 2. Negative "residual" loans (line `L_RECON`)

Cause: the loan maturity / repricing schedule (`LNRS3LES`, `LNRS3T12`, ... `LNOTOV15` — Schedule
RC-C Part I) is reported **gross**, not net of the allowance. The first version subtracted the
buckets from `LNLSNET` (net loans), giving a **negative** residual (about **−$16.5 billion** at
2026Q2) — economically meaningless, since loans cannot be negative.

Check: `LNLSNET = LNLSGR − LNATRES` exactly, and `LNLSGR − Σ(buckets)` is always **positive**,
stable at **0.5–0.7% of gross loans** across all 14 quarters (sensible: loans outside the
schedule, e.g. non-accrual loans).

Fix: `L_RECON` now starts from `LNLSGR`, and a separate line `A_ALLOW` = `−LNATRES` carries the
allowance explicitly (a contra-asset with no RSF weight of its own, since it is not an economic
liquidity exposure).

**Basis for loan RSF**: the NSFR applies RSF factors to **carrying (net) value**, not gross.
Because the `LNRS*/LNOT*` schedule exists only on a gross basis, `lcr_engine.py` multiplies every
`group=loans` line by the netting factor `LNLSNET / LNLSGR` (≈98.3% at 2026Q2, varies by
quarter) **before** applying `nsfr_rsf`. This approximates net-basis RSF while keeping the
maturity detail of the gross schedule. It is applied in the calculation step, not stored in
`liquidity_mapping.csv`, because the factor changes every quarter.

### 3. NSFR missing the RSF on undrawn commitments (lines `O_*`)

Basel NSFR requires **5% RSF on the undrawn portion of irrevocable and conditionally revocable
credit and liquidity facilities**; RSF on other contingent funding obligations (unconditionally
cancellable facilities, guarantees, letters of credit) is left to national discretion. The first
version gave off-balance-sheet lines an LCR outflow only, so this RSF was missing.

Fix: `O_HELOC`, `O_CRE`, `O_OTHER` (committed facilities) now carry 5% RSF; `O_CARD` (credit card
lines, unconditionally cancellable) and `O_SBLC` (standby letters of credit and guarantees) carry
0% under the national-discretion option, with the reason in `rationale` (5% on `O_SBLC` is a
sensitivity item; 5% on card lines would add about $56B of RSF). Effect: NSFR is 2.1–2.9pp lower
in every quarter (2026Q2: 115.1% → 112.9%); LCR is unchanged.

## Other major assumptions to be aware of

1. **LCR inflows are mostly not modelled** — 0% by default except `L_NBFI_SHORT`. Conservative;
   pushes the proxy LCR **down**. For reverse repos (`A_REVREPO`) 0% is actually the correct
   Basel factor if the collateral is Level 1 (LCR40.79); the collateral mix is unknown.
2. **Trading liabilities / derivatives** (`B_TRADEL`) **have no LCR outflow** — for a bank with
   JPMorgan's trading activity this could be a material missing outflow (pushes the proxy
   **up**, opposite to assumption 1).
3. **Pledged securities** (`M_SCPLEDGE`, $78.2B at 2026Q2) are a memo line and are **not deducted
   from HQLA**. Under the US rule, securities pledged to a Federal Reserve Bank but not used to
   secure borrowing remain eligible HQLA, and the Call Report does not show who holds the
   pledge. Full deduction is tested as an omission test (−7.0pp LCR).
4. **Uniform maturity** for aggregated `<=1 year` lines (30/365 assumed to fall inside the first
   30 days), because the Call Report does not split many funding lines below the 1-year mark.

All other assumptions (including the 18/48 `confidence=Low` lines) are written per line in the
`rationale` column of the CSV, rather than repeated here, to avoid two sources drifting apart.

## Sensitivity and benchmark (validating the baseline before stress testing)

The baseline was validated in two steps before designing stress scenarios — stressing a number
that is itself an uncertain estimate (18/48 lines `confidence=Low`) stacks two layers of
uncertainty without any way to tell which layer contributes what.

### 1. One-at-a-time sensitivity on `confidence=Low` lines, 2026Q2

Baseline: LCR = 85.0%, NSFR = 112.9%. Each line is moved between two values that Basel would
allow for the alternative category the line could belong to (`src/sensitivity.py`, dict
`BOUNDS`), holding all other lines constant. **Δ = (ratio at the high factor) − (ratio at the low
factor)**, i.e. the width of the range caused by that assumption alone, not the change from the
current baseline (the baseline sits somewhere between the two bounds).

| Line (bounds tested) | Δ LCR (pp) | Line (bounds tested) | Δ NSFR (pp) |
|---|---:|---|---:|
| `D_FO_IPC` (outflow 25%→100%) | −23.9 | `A_TRADE` (RSF 15%→100%) | −39.9 |
| `A_CASH_FOREIGN` (haircut 0%→100%) | −21.7 | `D_DOM_FOR` (ASF 0%→50%) | +2.5 |
| `O_OTHER` (outflow 10%→50%) | −19.4 | `A_CASH_FOREIGN` (RSF 0%→15%) | −2.0 |
| `B_REPO` (outflow 0%→100%) | −17.7 | 8 other lines | <1.5 each |
| `L_NBFI_SHORT` (inflow 0%→100%) | +16.3 | | |
| `L_OTH_LE12` (inflow 0%→15.3%*) | +10.8 | | |
| `D_DOM_FOR` (outflow 40%→100%) | −4.9 | | |
| `A_REVREPO` (inflow 0%→15%) | +4.9 | | |
| `B_OTHL`, `S_MUNI`, `O_SBLC` | <3.5 each | | |

\* 15.3% = Basel's 50% inflow rate applied only to the part of the line that can mature within
30 days (30/90 of the ≤3-month bucket, the same uniform-maturity rule used for `L_NBFI_SHORT`),
expressed as a rate on the whole line.

**Theoretical ceilings (not to be quoted as evidence).** If the two zero-inflow lines were given
their maximum conceivable inflow — 50% on the whole ≤12-month `L_OTH_LE12` line, ignoring
maturity, and 100% on all $407B of reverse repos (all collateral non-HQLA and all maturing within
30 days) — LCR would rise by +49.1pp and +48.2pp respectively. An earlier version of this README
used these numbers to argue that the two assumptions could explain the benchmark gap. That was
overstated: the maturity-consistent, Basel-plausible effects are +10.8pp and +4.9pp.

**Omission tests.** `B_TRADEL` (trading liabilities, currently no outflow): 20% / 50% / 100%
outflow lowers LCR by 2.5 / 6.0 / 11.1pp. `M_SCPLEDGE` (pledged securities, currently kept in
HQLA): full deduction from Level 1 lowers LCR by 7.0pp (85.0% → 78.1%).

**Combined envelope**: pushing all 22 plausible bounds on the 17 tested lines in the same
direction at once gives LCR 35.7%–180.0% and NSFR 104.0%–157.3%. **This is a theoretical outer
limit, not a confidence interval** (the chance that all 17 assumptions are wrong in the same
direction is close to zero) — quote the one-at-a-time table above instead.

Not tested one-at-a-time: `B_TRADEL` (covered by the omission test). All other 17 Low-confidence
lines are tested. Full results: `data/processed/sensitivity_results.csv`
(column `test_type`: plausible / ceiling / omission / envelope).

### 2. Benchmark against the LCR disclosed by JPMorgan Chase Bank, N.A. (all 14 quarters)

| Quarter | Proxy LCR | Disclosed LCR (bank, average) | Gap (pp) |
|---|---:|---:|---:|
| 23Q1 | 113.2% | 140% | −26.8 |
| 23Q2 | 105.3% | 129% | −23.7 |
| 23Q3 | 104.9% | 123% | −18.1 |
| 23Q4 | 117.5% | 129% | −11.5 |
| 24Q1 | 107.3% | 129% | −21.7 |
| 24Q2 | 105.6% | 125% | −19.4 |
| 24Q3 | 95.7% | 121% | −25.3 |
| 24Q4 | 107.7% | 124% | −16.3 |
| 25Q1 | 97.2% | 124% | −26.8 |
| 25Q2 | 100.1% | 120% | −19.9 |
| 25Q3 | 91.7% | 117% | −25.3 |
| 25Q4 | 95.3% | 115% | −19.7 |
| 26Q1 | 90.5% | 120% | −29.5 |
| 26Q2 | 85.0% | 118% | −33.0 |

Source of the disclosed figures: JPMorgan Chase & Co. Form 10-Q (SEC EDGAR, CIK 0000019617),
"Consolidated financial highlights" table, row "JPMorgan Chase Bank, N.A. LCR (average)" — the
10-Qs for 1Q24 (covers 23Q1–24Q1), 1Q25 (24Q2–25Q1) and 2Q26 (25Q2–26Q2). Note: the disclosed
figure is a **quarterly average**, while the proxy uses **quarter-end** balances — a method
difference, not only a data-granularity difference.

**Reading the benchmark**:
- The proxy is **below the disclosed LCR in every quarter, by 11.5–33.0pp** (average −22.6pp). The
  gap is wider in the two most recent quarters (−29.5 and −33.0pp) but not on a steady trend.
- The proxy **tracks the direction** reasonably well: correlation of levels 0.79, and both
  series move the same way in 8 of the 11 quarter-on-quarter changes where the disclosed LCR
  moved.
- **The gap cannot be attributed to a single assumption.** Within plausible Basel bounds no
  single line moves the LCR by more than ~24pp, and the gap comes from several sources that
  public data cannot separate: conservative inflow assumptions (`L_OTH_LE12`, `A_REVREPO`,
  `L_NBFI_SHORT`), conservative outflow choices (e.g. `D_DOM_FOR` at 100%), Basel factors vs the
  US rule, average vs quarter-end balances — partly offset by choices acting in the opposite
  direction (`B_TRADEL` omitted, `A_CASH_FOREIGN` treated as Level 1, pledged securities kept in
  HQLA).
- The baseline is **deliberately not tuned** to close the gap: keeping consistent, conservative
  Basel assumptions is easier to defend than calibrating to one bank's disclosed number (risk of
  overfitting).

**Where the file comes from**: the disclosed LCR column is **manual input** from the filings
(`src/benchmark.py`, dict `REAL_LCR`), not computed; the script only joins it with the proxy from
`ratios_by_quarter.csv` and computes the gap. NSFR **has no benchmark**, so the NSFR proxy has not
been validated against a disclosed figure.

Full data: `data/processed/lcr_benchmark.csv`.

## Data scope and units

- All amounts are in **USD thousands** (FDIC unit). Example: 957,000,000 means $957 billion.
- The data is the Call Report of **JPMorgan Chase Bank, N.A. only** (solo), not the consolidated
  report of JPMorgan Chase & Co.
- Mapping factors follow Basel (BCBS 238/295); only the securities classification is
  cross-checked with Reg WW. The disclosed LCR used for the benchmark follows the US rule, so part
  of the gap is a method difference, not only a data-detail difference.

## Ratio formulas (implemented in `src/lcr_engine.py`)

```
HQLA by level   = Σ(asset_value × (1 − haircut))                over lines with hqla_level = L1 / L2A / L2B
HQLA            = L1 + L2A + L2B − cap adjustment               Basel LCR30.45–30.46 (simplified)
cap adjustment  = max(L2A + L2B − 2/3 × L1,  L2B − 15/85 × (L1 + L2A),  0)
                  → Level 2 ≤ 40% of HQLA, Level 2B ≤ 15% of HQLA (not binding in this data)
LCR outflow     = Σ(liability_value × lcr_outflow) + Σ(offbs_value × lcr_outflow)
LCR inflow      = Σ(asset_value × lcr_inflow)
LCR             = HQLA / max(LCR outflow − LCR inflow, 25% × LCR outflow)   [inflow cap 75%]

ASF             = Σ(liability_value × nsfr_asf) + Σ(equity_value × nsfr_asf)
RSF             = Σ(asset_value × nsfr_rsf × k) + Σ(offbs_undrawn × nsfr_rsf)
                  [k = LNLSNET / LNLSGR for group=loans, else 1]
NSFR            = ASF / RSF

LDR             = LNLSNET / DEP
```

Each line contributes only through the roles it has (off-balance-sheet lines are not part of the
balance-sheet total but do add to LCR outflows and NSFR RSF; memo lines contribute to nothing).
