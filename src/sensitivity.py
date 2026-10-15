"""
Sensitivity analysis on the latest quarter (2026Q2).

Three kinds of test, kept apart on purpose (column test_type in the output):

  1. "plausible"  One-at-a-time (OAT) on every confidence='Low' mapping row that has a factor to
                  test (17 of 18 -- see "Not tested" below). Each row moves between two values
                  that Basel would actually allow for the category the line could belong to,
                  holding everything else at baseline. These are the numbers to quote.

  2. "ceiling"    Theoretical upper limits for the two zero-inflow assumptions (L_OTH_LE12,
                  A_REVREPO). They ignore the 30-day maturity filter and/or assume the least
                  favourable collateral, so they overstate the realistic effect. Shown only to
                  explain why the plausible bound is much smaller -- do not quote as evidence.

  3. "omission"   Items that are left out of the baseline rather than calibrated:
                  - B_TRADEL (trading liabilities): no LCR outflow in baseline
                  - M_SCPLEDGE (pledged securities): NOT deducted from HQLA in baseline. Under
                    the US rule, securities pledged to a Federal Reserve Bank but not used to
                    secure any borrowing remain eligible HQLA, and the Call Report does not say
                    who holds the pledge, so the baseline keeps them; this test shows the
                    effect of the opposite (fully encumbered) assumption.

Plus a combined envelope: all "plausible" bounds pushed in the same direction at once.

Not tested in OAT: B_TRADEL (covered by the omission test instead).
"""
import csv

from lcr_engine import compute, line_value, load_mapping, load_wide

OUT_PATH = "data/processed/sensitivity_results.csv"

mapping = load_mapping()
latest = load_wide()[-1]  # 2026Q2


def ratios(overrides=None, l1_deduction=0.0):
    r = compute(latest, mapping, overrides, extra_l1_deduction=l1_deduction)
    return r["LCR"], r["NSFR"]


baseline_lcr, baseline_nsfr = ratios()
print(f"Baseline ({latest['report_period']}): LCR={baseline_lcr:.1f}%  NSFR={baseline_nsfr:.1f}%\n")

# Maturity-consistent inflow rate for L_OTH_LE12: Basel allows 50% inflow on retail/non-financial
# loans only for the part that CONTRACTUALLY MATURES within 30 days. Of this line, only the <=3m
# bucket can mature in 30 days; with the same uniform-maturity assumption used for L_NBFI_SHORT,
# 30/90 of that bucket does. Expressed as an effective rate on the whole line value:
v_le3m = line_value(latest, "LNOT3LES-min(LNNDEPD,LNOT3LES)")
v_line = line_value(latest, "LNOT3LES+LNOT3T12-min(LNNDEPD,LNOT3LES)")
L_OTH_EFF = 0.50 * (30 / 90) * v_le3m / v_line

# (field, low, high, note). "low"/"high" are factor values, not "better"/"worse".
BOUNDS = {
    "A_CASH_FOREIGN": [
        ("hqla_haircut", 0.0, 1.0, "L1 central-bank reserve (0% haircut, current) vs ordinary correspondent balance, not HQLA"),
        ("nsfr_rsf", 0.0, 0.15, "central-bank reserve (0% RSF, current) vs FI placement <6m (15% RSF)"),
    ],
    "A_CIPC": [("nsfr_rsf", 0.0, 1.0, "near-cash, clears fast (0%) vs conservative 'other asset' (100%, current)")],
    "S_MUNI": [
        ("hqla_haircut", 0.5, 1.0, "investment-grade GO muni, L2B (50%, current) vs not HQLA"),
        ("nsfr_rsf", 0.5, 0.85, "L2B RSF (50%, current) vs non-HQLA RSF (85%)"),
    ],
    "S_OTHDOM": [("nsfr_rsf", 0.65, 1.0, "eligible >=1y non-HQLA bond (65%) vs unrated/equity-like (100%); current 85%")],
    "S_FOR": [("nsfr_rsf", 0.65, 1.0, "could include eligible foreign sovereign debt (65%) vs fully unrated (100%); current 85%")],
    "S_OTHER": [("nsfr_rsf", 0.65, 1.0, "same bracket as above; current 85%")],
    "A_TRADE": [("nsfr_rsf", 0.15, 1.0, "securities-like trading book (15%) vs derivative-like (100%); current 85%")],
    "A_REVREPO": [
        ("lcr_inflow", 0.0, 0.15, "Level 1 collateral (0%, current, Basel LCR40.79) vs Level 2A collateral (15%), assuming all matures <=30d"),
        ("nsfr_rsf", 0.10, 0.15, "L1-collateralised (10%) vs other collateral <6m (15%, current)"),
    ],
    "L_NBFI_SHORT": [("lcr_inflow", 0.0, 1.0, "no credit (0%) vs whole line maturing <=30d (100%); current 33% = 30/90")],
    "L_OTH_LE12": [("lcr_inflow", 0.0, round(L_OTH_EFF, 4),
                    f"no credit (0%, current) vs 50% inflow on the 30/90 share of the <=3m bucket (= {L_OTH_EFF*100:.1f}% of the line)")],
    "L_RECON": [("nsfr_rsf", 0.65, 1.0, "mostly performing, just unscheduled (65%) vs non-performing (100%); current 85%")],
    "D_DOM_FOR": [
        ("lcr_outflow", 0.4, 1.0, "mostly foreign govt / official, non-operational (40%) vs foreign banks (100%, current)"),
        ("nsfr_asf", 0.0, 0.5, "foreign banks (0%, current) vs govt / official (50%)"),
    ],
    "D_FO_IPC": [("lcr_outflow", 0.25, 1.0, "operational corporate deposit (25%) vs non-bank FI (100%); current 40%")],
    "B_REPO": [("lcr_outflow", 0.0, 1.0, "fully L1-collateralised (0%) vs other collateral (100%); current 25%")],
    "B_OTHL": [("lcr_outflow", 0.0, 0.2, "pure accruals/payables (0%, current) vs some near-term funding mixed in (20%)")],
    "O_OTHER": [("lcr_outflow", 0.10, 0.50, "mostly corporate credit facility (10%) vs liquidity/FI facility mix (50%); current 20%")],
    "O_SBLC": [
        ("lcr_outflow", 0.05, 0.20, "trade-related SBLC (5%, current) vs financial guarantee (20%)"),
        ("nsfr_rsf", 0.0, 0.05, "national discretion: 0% (current) vs treated like a committed facility (5%)"),
    ],
}

CEILINGS = [
    ("L_OTH_LE12", "lcr_inflow", 0.0, 0.5,
     "CEILING: 50% inflow on the WHOLE <=12m line, ignoring that most of it does not mature within 30 days"),
    ("A_REVREPO", "lcr_inflow", 0.0, 1.0,
     "CEILING: 100% inflow on all reverse repos = all collateral non-HQLA AND all maturing <=30d"),
]

out_rows = []


def record(test_type, lid, field, lo, hi, note, res_lo, res_hi):
    (lcr_lo, nsfr_lo), (lcr_hi, nsfr_hi) = res_lo, res_hi
    out_rows.append(dict(test_type=test_type, line_id=lid, field=field, low=lo, high=hi, note=note,
                         LCR_at_low=round(lcr_lo, 2), LCR_at_high=round(lcr_hi, 2),
                         delta_LCR_pp=round(lcr_hi - lcr_lo, 2),
                         NSFR_at_low=round(nsfr_lo, 2), NSFR_at_high=round(nsfr_hi, 2),
                         delta_NSFR_pp=round(nsfr_hi - nsfr_lo, 2)))
    print(f"{test_type:9s} {lid:15s} {field:13s} {lcr_lo:7.1f} {lcr_hi:7.1f} {lcr_hi-lcr_lo:+8.2f}   "
          f"{nsfr_lo:7.1f} {nsfr_hi:7.1f} {nsfr_hi-nsfr_lo:+8.2f}")


print(f"{'type':9s} {'line_id':15s} {'field':13s} {'LCR@lo':>7s} {'LCR@hi':>7s} {'dLCR':>8s}   "
      f"{'NSFR@lo':>7s} {'NSFR@hi':>7s} {'dNSFR':>8s}")

# 1. plausible OAT
for lid, specs in BOUNDS.items():
    for field, lo, hi, note in specs:
        record("plausible", lid, field, lo, hi, note, ratios({lid: {field: lo}}), ratios({lid: {field: hi}}))

# 2. ceilings
for lid, field, lo, hi, note in CEILINGS:
    record("ceiling", lid, field, lo, hi, note, ratios({lid: {field: lo}}), ratios({lid: {field: hi}}))

# 3. omissions
for pct in (0.20, 0.50, 1.00):
    record("omission", "B_TRADEL", "lcr_outflow", 0.0, pct,
           f"trading liabilities omitted (0%, current) vs {pct*100:.0f}% outflow", ratios(), ratios({"B_TRADEL": {"lcr_outflow": pct}}))
pledged = line_value(latest, "SCPLEDGE")
record("omission", "M_SCPLEDGE", "l1_deduction", 0.0, 1.0,
       f"pledged securities (${pledged/1e6:,.1f}B) kept in HQLA (current) vs fully deducted from Level 1",
       ratios(), ratios(l1_deduction=pledged))

# 4. combined envelope over the plausible bounds only
def extreme(metric_idx, direction):
    ov = {}
    for lid, specs in BOUNDS.items():
        for field, lo, hi, _ in specs:
            r_lo = ratios({lid: {field: lo}})[metric_idx]
            r_hi = ratios({lid: {field: hi}})[metric_idx]
            pick_lo = (r_lo < r_hi) if direction == "worst" else (r_lo > r_hi)
            ov.setdefault(lid, {})[field] = lo if pick_lo else hi
    return ratios(ov)[metric_idx]


lcr_w, lcr_b = extreme(0, "worst"), extreme(0, "best")
nsfr_w, nsfr_b = extreme(1, "worst"), extreme(1, "best")
print(f"\nCombined envelope (all {sum(len(s) for s in BOUNDS.values())} plausible bounds on "
      f"{len(BOUNDS)} Low-confidence lines pushed together):")
print(f"  LCR : {lcr_w:.1f}% .. {lcr_b:.1f}%   (baseline {baseline_lcr:.1f}%)")
print(f"  NSFR: {nsfr_w:.1f}% .. {nsfr_b:.1f}%   (baseline {baseline_nsfr:.1f}%)")

out_rows.append(dict(test_type="envelope", line_id="ALL_PLAUSIBLE", field="all", low="worst", high="best",
                     note="every plausible bound pushed in the same direction at once; theoretical outer limit, not a confidence interval",
                     LCR_at_low=round(lcr_w, 2), LCR_at_high=round(lcr_b, 2), delta_LCR_pp=round(lcr_b - lcr_w, 2),
                     NSFR_at_low=round(nsfr_w, 2), NSFR_at_high=round(nsfr_b, 2), delta_NSFR_pp=round(nsfr_b - nsfr_w, 2)))
with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)
print(f"\nWrote {OUT_PATH} ({len(out_rows)} rows)")
