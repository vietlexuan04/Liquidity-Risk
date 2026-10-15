"""Build mapping/liquidity_mapping.csv + reconcile it against the wide FDIC data.
All amounts in USD thousands (FDIC unit). Rates are decimals.
Columns: line_id, side, group, definition (formula over FDIC mnemonics), description,
hqla_level, hqla_haircut, lcr_outflow, lcr_inflow, nsfr_asf, nsfr_rsf, in_balance_sum,
confidence, rationale, source
"""
import csv

D30 = 30/365  # share of <=1y maturities assumed to fall inside 30 days (uniform-maturity assumption)
BASEL_LCR = "Basel LCR (BCBS 238; Basel Framework LCR30/LCR40)"
BASEL_NSFR = "Basel NSFR (BCBS 295; Basel Framework NSF30)"
WW = "US Reg WW (12 CFR 249) HQLA treatment"

def R(line_id, side, group, definition, desc, hl="", hh="", out="", inn="", asf="", rsf="", bal=1, conf="Medium", why="", src=""):
    return dict(line_id=line_id, side=side, group=group, definition=definition, description=desc,
                hqla_level=hl, hqla_haircut=hh, lcr_outflow=out, lcr_inflow=inn, nsfr_asf=asf, nsfr_rsf=rsf,
                in_balance_sum=bal, confidence=conf, rationale=why, source=src)

rows = [
# ---------------- ASSETS ----------------
R("A_RES_FED","asset","cash","CHFRB","Balances at Federal Reserve (central bank reserves)","L1",0,inn=0,rsf=0,conf="High",
  why="Central bank reserves = Level 1, 0% haircut; 0% RSF",src=BASEL_LCR+" LCR30.1; "+BASEL_NSFR),
R("A_CASH_FOREIGN","asset","cash","CHNUS","Balances due from foreign banks (assumed mostly foreign central bank placements)","L1",0,rsf=0,conf="Low",
  why="Not separable in Call Report; assumed foreign central-bank reserves for a G-SIB bank. Sensitivity: set haircut/RSF to FI-placement values",
  src="Assumption - verify vs JPMorgan Chase & Co. LCR disclosure"),
R("A_COIN","asset","cash","CHCOIN","Currency and coin","L1",0,rsf=0,conf="High",why="Coins and banknotes = Level 1",src=BASEL_LCR),
R("A_CIPC","asset","cash","CHCIC","Cash items in process of collection, unposted debits and currency & coin (RC-A item 1)","","",rsf=1.0,conf="Low",
  why="Not HQLA; conservative 'other assets' RSF. Contains currency & coin, which is backed out by A_CASH_SCOPE_ADJ and counted "
      "in A_COIN; the remainder (items in collection + foreign-office currency) stays non-HQLA, a slightly conservative choice",src=BASEL_NSFR),
R("A_CASH_SCOPE_ADJ","asset","cash","-CHCOIN","Scope adjustment: CHCOIN is already included in CHCIC","","",rsf=0.0,conf="High",
  why="Empirically verified at all 14 quarters: CHBAL == CHFRB+CHNUS+CHUS+CHCIC exactly, with no room for CHCOIN; "
      "and total ASSET only reconciles when CHCOIN is NOT added as an incremental amount on top of CHBAL's 4 sub-items. "
      "Root cause confirmed: CHBAL's components follow FFIEC 031 Schedule RC-A, whose item 1 (MDRM RCFD0022) is "
      "'Cash items in process of collection, unposted debits, AND currency and coin' = items 0020 + 0080. So CHCIC already "
      "contains currency and coin, and CHCOIN (RCON0080, domestic offices) is a sub-item of it (CHCIC >= CHCOIN in all 14 "
      "quarters). This line backs CHCOIN out of the cash total so it is counted once, in A_COIN (Level 1 HQLA).",
  src="FFIEC 031 Schedule RC-A; Federal Reserve MDRM item RCFD0022; see mapping_README.md 'Issues found in review'"),
R("A_DUE_US","asset","cash","CHUS","Balances due from US depository institutions","","",rsf=0.15,conf="Medium",
  why="Placements with financial institutions <6m: 15% RSF",src=BASEL_NSFR),
R("S_UST","asset","securities","SCUST","US Treasury securities","L1",0,rsf=0.05,conf="High",
  why="Sovereign 0% RW = Level 1; unencumbered L1 RSF 5%",src=BASEL_LCR+" LCR30.1; "+BASEL_NSFR),
R("S_GNMA","asset","securities","SCGNM","GNMA pass-through MBS (full faith & credit)","L1",0,rsf=0.05,conf="Medium",
  why="Treated as Level 1 under US rule (Treasury-guaranteed); Basel text is less explicit -> flagged",src=WW),
R("S_GSE","asset","securities","SCUSO-SCGNM","Agency/GSE debt and MBS (FNMA, FHLMC, agency CMO/CMBS)","L2A",0.15,rsf=0.15,conf="Medium",
  why="GSE-guaranteed securities = Level 2A, 15% haircut; RSF 15%",src=BASEL_LCR+" LCR30.1; "+WW),
R("S_MUNI","asset","securities","SCMUNI","State & municipal securities","L2B",0.50,rsf=0.50,conf="Low",
  why="Investment-grade GO munis Level 2B (50% haircut) under US rule; ratings unknown",src=WW),
R("S_OTHDOM","asset","securities","SCDOMO","Other domestic debt (private RMBS/CMBS, ABS, structured, corporate)","","",rsf=0.85,conf="Low",
  why="No ratings -> not HQLA (conservative); non-HQLA securities RSF 85%",src=BASEL_NSFR),
R("S_FOR","asset","securities","SCFORD","Foreign debt securities","","",rsf=0.85,conf="Low",
  why="Composition unknown (foreign sovereign could be L1) -> conservative non-HQLA; sensitivity item",src="Assumption"),
R("S_OTHER","asset","securities","SC-SCUST-SCUSO-SCMUNI-SCDOMO-SCFORD","Equities & residual securities, net of the HTM credit-loss allowance (can be slightly negative, e.g. 2023Q1)","","",rsf=0.85,conf="Low",
  why="Equity/residual: not HQLA, RSF 85%",src=BASEL_NSFR),
R("A_TRADE","asset","trading","TRADE","Trading assets","","",rsf=0.85,conf="Low",
  why="Composition (securities vs derivatives) unknown; blended 85%. Derivative assets would be 100%",src=BASEL_NSFR),
R("A_REVREPO","asset","secured_lending","FREPO","Fed funds sold & reverse repos","","",inn=0,rsf=0.15,conf="Low",
  why="Secured lending to FIs <6m: 10% (L1 collateral) / 15% (other) -> 15% conservative. LCR inflow 0%: correct under Basel LCR40.79 "
      "if the collateral is Level 1 (15% for L2A, 100% for non-HQLA); collateral mix and maturity unknown -> sensitivity item",src=BASEL_NSFR+"; "+BASEL_LCR+" LCR40.79"),
R("L_RES_LE12","asset","loans","LNRS3LES+LNRS3T12","1-4 family first-lien loans, <=12m (maturity/repricing)","","",rsf=0.50,conf="Medium",
  why="Loans <1y to retail: 50% RSF",src=BASEL_NSFR),
R("L_RES_GT12","asset","loans","LNRS1T3+LNRS3T5+LNRS5T15+LNRSOV15","1-4 family first-lien loans, >1y","","",rsf=0.65,conf="Medium",
  why="Residential mortgages >=1y, RW<=35%: 65% RSF. Note buckets are 'maturity OR next repricing' (ARMs understate maturity)",src=BASEL_NSFR),
R("L_NBFI_SHORT","asset","loans","min(LNNDEPD,LNOT3LES)","Loans to non-depository financial institutions (assumed <=3m)","","",inn=D30/ (90/365),rsf=0.15,conf="Low",
  why="Loans to FIs <6m: 15% RSF; FI inflow 100% x (30d/90d) share maturing in 30d",src=BASEL_NSFR+"; "+BASEL_LCR),
R("L_OTH_LE12","asset","loans","LNOT3LES+LNOT3T12-min(LNNDEPD,LNOT3LES)","Other loans <=12m (C&I, cards, consumer, other)","","",inn=0,rsf=0.50,conf="Low",
  why="Loans <1y to non-financials/retail: 50% RSF. LCR inflow 0%: Basel allows 50% only on amounts contractually maturing within 30 days, "
      "and the <=3m bucket is dominated by revolving/no-maturity balances (cards, revolvers) -> no inflow credited (conservative; sensitivity item)",src=BASEL_NSFR+"; "+BASEL_LCR),
R("L_OTH_GT12","asset","loans","LNOT1T3+LNOT3T5+LNOT5T15+LNOTOV15","Other loans >1y","","",rsf=0.85,conf="Medium",
  why="Performing loans >=1y, RW>35%: 85% RSF",src=BASEL_NSFR),
R("L_RECON","asset","loans","LNLSGR-(LNRS3LES+LNRS3T12+LNRS1T3+LNRS3T5+LNRS5T15+LNRSOV15+LNOT3LES+LNOT3T12+LNOT1T3+LNOT3T5+LNOT5T15+LNOTOV15)",
  "Loans not covered by the maturity/repricing schedule (gross basis)","","",rsf=0.85,conf="Low",
  why="The LNRS*/LNOT* maturity schedule (Sched. RC-C Pt.I memo) is reported GROSS, not net of allowance -- confirmed: "
      "LNLSNET = LNLSGR - LNATRES exactly, and LNLSGR - sum(buckets) is small and POSITIVE (~0.6% of gross loans, sensible "
      "residual e.g. nonaccrual/unscheduled loans), whereas LNLSNET - sum(buckets) was NEGATIVE (impossible economically) -- "
      "that was the bug. Fixed by using LNLSGR as the base here; the allowance is now backed out explicitly via A_ALLOW below "
      "instead of being silently mixed into this residual.",
  src="Reconciliation-forced fix; see mapping_README.md 'Known data quirks'"),
R("A_ALLOW","asset","loans","-LNATRES","Allowance for loan and lease losses (contra-asset)","","",rsf="",conf="High",
  why="Deduction from gross to net loan carrying value (LNLSNET = LNLSGR - LNATRES). Not an economic exposure, so no RSF "
      "weight of its own -- lcr_engine.py excludes this line from the RSF-weighted sum but includes it in the balance-sheet "
      "total check. NSFR RSF is properly applied on carrying (net) values, not gross: lcr_engine.py applies a uniform "
      "LNLSNET/LNLSGR netting factor across all loan-schedule RSF lines to approximate this (see mapping_README.md).",
  src="Standard netting (carrying-value basis)"),
R("A_PREM","asset","other","BKPREM","Premises & fixed assets","","",rsf=1.0,conf="High",why="Other assets 100% RSF",src=BASEL_NSFR),
R("A_ORE","asset","other","ORE","Other real estate owned","","",rsf=1.0,conf="High",why="Other assets 100% RSF",src=BASEL_NSFR),
R("A_INTAN","asset","other","INTAN","Goodwill & intangibles","","",rsf=1.0,conf="High",why="Other assets 100% RSF",src=BASEL_NSFR),
R("A_OTHER","asset","other","AOA","All other assets","","",rsf=1.0,conf="Medium",why="Other assets 100% RSF",src=BASEL_NSFR),
# ---------------- LIABILITIES ----------------
R("D_INS_STABLE","liability","deposits","DEPINS-BROINS","Insured domestic deposits (non-brokered) - proxy for stable retail/small business","","",out=0.05,asf=0.95,conf="Medium",
  why="Fully insured deposits = 'stable' 5% run-off; stable retail <1y ASF 95%. Proxy: assumes relationship criteria met",src=BASEL_LCR+" LCR40.7; "+BASEL_NSFR),
R("D_INS_BRO","liability","deposits","BROINS","Fully insured brokered deposits","","",out=0.10,asf=0.90,conf="Medium",
  why="Brokered -> less stable: 10% run-off; ASF 90%",src=BASEL_LCR+" LCR40.9; "+BASEL_NSFR),
R("D_DOM_BANK","liability","deposits","TRNCBO+NTRCOMOT","Deposits of US banks (domestic offices)","","",out=1.00,asf=0.0,conf="High",
  why="Financial institution deposits 100% run-off; ASF 0%",src=BASEL_LCR+" LCR40.28; "+BASEL_NSFR),
R("D_DOM_GOV","liability","deposits","TRNUSGOV+NTRUSGOV+TRNMUNI+NTRMUNI","US federal/state/local govt deposits","","",out=0.40,asf=0.50,conf="Medium",
  why="Sovereign/PSE non-operational 40% run-off; wholesale <1y ASF 50%",src=BASEL_LCR+" LCR40.31; "+BASEL_NSFR),
R("D_DOM_FOR","liability","deposits","TRNFCFG+NTRFCFG","Foreign banks & govts' deposits in domestic offices","","",out=1.00,asf=0.0,conf="Low",
  why="Mix of foreign banks (100%) and foreign govts (40%) unknown -> conservative 100%",src="Assumption"),
R("D_DOM_UNINS_OTH","liability","deposits","DEPDOM-DEPINS-(TRNCBO+NTRCOMOT)-(TRNUSGOV+NTRUSGOV+TRNMUNI+NTRMUNI)-(TRNFCFG+NTRFCFG)",
  "Uninsured domestic deposits - corporates & other (residual)","","",out=0.40,asf=0.50,conf="Medium",
  why="Non-financial corporate non-operational 40% run-off; ASF 50%. Operational-deposit share (25%) not separable -> sensitivity",src=BASEL_LCR+" LCR40.31; "+BASEL_NSFR),
R("D_FO_IPC","liability","deposits","DEPIPCCF","Foreign-office deposits: individuals/partnerships/corporations","","",out=0.40,asf=0.50,conf="Low",
  why="Assumed non-financial corporate/wholesale; may include non-bank FIs (100%)",src="Assumption"),
R("D_FO_BANK","liability","deposits","DEPFBKF+DEPUSBKF","Foreign-office deposits: banks","","",out=1.00,asf=0.0,conf="High",
  why="FI deposits 100% run-off; ASF 0%",src=BASEL_LCR),
R("D_FO_GOV","liability","deposits","DEPFGOVF+DEPUSMF","Foreign-office deposits: governments/official","","",out=0.40,asf=0.50,conf="Medium",
  why="Sovereign non-operational 40%; ASF 50%",src=BASEL_LCR),
R("B_REPO","liability","borrowings","FREPP","Fed funds purchased & repos","","",out=0.25,asf=0.0,conf="Low",
  why="Secured funding; collateral mix unknown. L1 0% / L2A 15% / other up to 100% -> 25% placeholder. ASF 0% (<6m FI)",src=BASEL_LCR+" LCR40.46-40.50"),
R("B_TRADEL","liability","borrowings","TRADEL","Trading liabilities","","",out=0.0,asf=0.0,conf="Low",
  why="Derivative/short-position outflows not reconstructable from Call Report -> omitted (understates outflows)",src="Limitation"),
R("B_ST","liability","borrowings","OTHBOT1L+OTBFH1L","Other borrowings + FHLB advances maturing <=1y","","",out=D30,asf=0.25,conf="Medium",
  why="Uniform maturity: 30/365 falls in 30d at 100%; ASF avg of 0% (<6m) and 50% (6-12m) = 25%",src=BASEL_LCR+"; "+BASEL_NSFR),
R("B_LT","liability","borrowings","OTHBRF-OTHBOT1L-OTBFH1L","Other borrowings with remaining maturity >1y","","",out=0.0,asf=1.0,conf="Medium",
  why="Liabilities >=1y: 100% ASF; no 30d outflow",src=BASEL_NSFR),
R("B_SUB","liability","borrowings","SUBND","Subordinated debt","","",out=0.0,asf=1.0,conf="High",why="Capital/long-term debt 100% ASF",src=BASEL_NSFR),
R("B_OTHL","liability","other","ALLOTHL","All other liabilities","","",out=0.0,asf=0.0,conf="Low",
  why="Accruals/payables; other liabilities 0% ASF; LCR outflow omitted",src=BASEL_NSFR),
R("E_EQ","equity","capital","EQTOT","Total equity capital","","",out=0.0,asf=1.0,conf="High",
  why="Regulatory capital pre-deductions 100% ASF (equity used as proxy)",src=BASEL_NSFR),
# ---------------- OFF-BALANCE SHEET (LCR outflow + NSFR RSF on undrawn amounts; not in balance sums) ----------------
R("O_CARD","offbs","commitments","UCCRCD","Unused credit card lines","","",out=0.05,rsf=0.0,bal=0,conf="Medium",
  why="LCR: retail credit facilities 5%. NSFR: card lines are unconditionally cancellable; Basel leaves RSF on these to national "
      "discretion -> 0% (5% would add ~$56B RSF)",src=BASEL_LCR+" LCR40.57; "+BASEL_NSFR+" (off-balance-sheet RSF table)"),
R("O_HELOC","offbs","commitments","UCLOC","Unused HELOC lines","","",out=0.05,rsf=0.05,bal=0,conf="Medium",
  why="LCR: retail facilities 5%. NSFR: committed credit facility, 5% RSF on undrawn amount",src=BASEL_LCR+"; "+BASEL_NSFR+" (off-balance-sheet RSF table)"),
R("O_CRE","offbs","commitments","UCCOMRE","Unused CRE/construction commitments","","",out=0.10,rsf=0.05,bal=0,conf="Medium",
  why="LCR: corporate credit facilities 10%. NSFR: committed credit facility, 5% RSF on undrawn amount",src=BASEL_LCR+"; "+BASEL_NSFR+" (off-balance-sheet RSF table)"),
R("O_OTHER","offbs","commitments","UCOTHER","Other unused commitments","","",out=0.20,rsf=0.05,bal=0,conf="Low",
  why="LCR: blend of corporate credit 10% / liquidity 30% / FI 40-100% -> 20% placeholder. NSFR: committed credit/liquidity "
      "facilities, 5% RSF on undrawn amount",src=BASEL_LCR+"; "+BASEL_NSFR+" (off-balance-sheet RSF table)"),
R("O_SBLC","offbs","commitments","LOCFPSB","Standby letters of credit & guarantees","","",out=0.05,rsf=0.0,bal=0,conf="Low",
  why="LCR: contingent funding, national discretion; 5% placeholder. NSFR: other contingent funding obligations, national "
      "discretion -> 0% (sensitivity item)",src=BASEL_LCR+"; "+BASEL_NSFR+" (off-balance-sheet RSF table)"),
R("M_SCPLEDGE","memo","encumbrance","SCPLEDGE","Pledged securities (memo only -- NOT deducted from HQLA in the baseline)","","",bal=0,conf="Medium",
  why="Memo line, no ratio role. Pledged securities are not automatically encumbered: under the US rule, securities pledged to a "
      "Federal Reserve Bank but not used to secure borrowing remain eligible HQLA, and the Call Report does not show who holds "
      "the pledge. Baseline keeps them in HQLA; sensitivity.py tests full deduction from Level 1 (omission test).",src=BASEL_LCR+" LCR30.2; "+WW),
]

FIELDS = list(rows[0].keys())
with open("mapping/liquidity_mapping.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)

# ---- NHNN / Vietnam ratio definitions (separate table) ----
nhnn = [
 dict(ratio="LDR / CDR",threshold="<=85%",status="In force (LDR); draft replaces with CDR (draft 29/4/2026)",
      note="Loans / deposits. In force: State Treasury (KBNN) term deposits fully excluded from deposits from 2026 (TT 26/2022 roadmap). Draft CDR: numerator widened to credit extension (adds corporate bonds etc.) less eligible equity; denominator excludes interbank deposits, counts 20% of State Treasury term deposits",
      source="TT 22/2019/TT-NHNN (amended); draft replacement circular of 29/4/2026 (FPTS, ACBS summaries)"),
 dict(ratio="Short-term funding for medium/long-term loans (SFL)",threshold="<=40% from 01/07/2026 (30% from 01/10/2023)",status="In force",
      note="Raised from 30% to 40% by TT 25/2026/TT-NHNN (effective 01/07/2026), amending Article 16(5) of TT 22/2019",
      source="TT 25/2026/TT-NHNN; TT 22/2019/TT-NHNN"),
 dict(ratio="LCR",threshold="Draft roadmap: 70% (2028), 80% (2029), 90% (2030), 100% (2031)",status="Draft only (draft replacement of Circular 22, published 29/4/2026)",note="Bank applying LCR and NSFR and meeting 100% would be exempt from CDR (still reported) and from the Circular 22 ratios incl. SFL",source="Draft circular replacing TT 22/2019 (29/4/2026); FPTS update 05/2026; ACBS summary"),
 dict(ratio="NSFR",threshold="Draft roadmap: 90% (2028), 95% (2029), 100% (2030)",status="Draft only",note="",source="Draft circular replacing TT 22/2019 (29/4/2026); FPTS update 05/2026"),
 dict(ratio="Leverage (LEV)",threshold=">=3% (Tier 1 / total exposure)",status="Draft only",note="Monitoring only until the Governor decides to apply it",source="Draft circular replacing TT 22/2019 (29/4/2026); FPTS update 05/2026"),
]
with open("mapping/nhnn_ratio_reference.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(nhnn[0].keys())); w.writeheader(); w.writerows(nhnn)

# ---- reconciliation vs wide data ----
wide = list(csv.DictReader(open("data/processed/jpm_628_wide.csv")))
def val(row, expr):
    env = {k: float(v) if v not in ("", None) else 0.0 for k, v in row.items() if k != "report_period"}
    env["min"] = min
    return eval(expr, {"__builtins__": {}}, env)
print(f"{'quarter':10s} {'assets_gap':>14s} {'liab+eq_gap':>14s}   (USD thousands, should be ~0)")
worst = 0
for row in wide:
    a = sum(val(row, r["definition"]) for r in rows if r["side"]=="asset")
    l = sum(val(row, r["definition"]) for r in rows if r["side"] in ("liability","equity"))
    ga, gl = a - val(row,"ASSET"), l - val(row,"LIABEQ")
    worst = max(worst, abs(ga), abs(gl))
    print(f"{row['report_period']:10s} {ga:14,.0f} {gl:14,.0f}")
print("max abs gap:", f"{worst:,.0f}")
print("rows:", len(rows))
