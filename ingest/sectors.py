"""SIC code to sector mapping."""

from typing import Optional

# (low, high, sector) — inclusive range, first match wins.
#
# The single-SIC entries below come first because they override the broad ranges under them.
# They are not hand-picked: each was measured against GICS using the S&P 500 as ground truth
# (scripted, see the commit that added them). A code is carved out only when every S&P member
# of it disagrees with the range's answer, or when the range is right for almost none of them.
# SICs that are genuinely mixed -- 3823 holds Ametek, Keysight and Danaher; 7372 holds 15
# software names plus a bank -- are deliberately left to their range.
SIC_RANGES: list[tuple[int, int, str]] = [
    (1400, 1400, "Materials"),  # nonmetallic mineral mining: MLM, VMC
    (1520, 1531, "Consumer Discretionary"),  # homebuilders: DHI, NVR, PHM, LEN
    (2860, 2870, "Materials"),  # organic and agricultural chemicals: IFF, LYB, CF, MOS
    (3021, 3021, "Consumer Discretionary"),  # footwear: NKE, DECK
    (3420, 3420, "Industrials"),  # handtools and hardware: SNA, SWK
    (3663, 3663, "Technology"),  # broadcasting and comms equipment: QCOM, MSI
    (3724, 3730, "Industrials"),  # aircraft engines, ships: HON, RTX, GD, HII
    (4400, 4400, "Consumer Discretionary"),  # water transport is cruise lines: CCL, RCL, NCLH
    (4700, 4700, "Consumer Discretionary"),  # transport services is online travel: BKNG, EXPE
    (4922, 4922, "Energy & Mining"),  # gas transmission, not a utility: KMI, WMB, TRGP
    (4953, 4953, "Industrials"),  # refuse systems: WM, RSG
    (5122, 5122, "Health Care"),  # drug wholesale: MCK, CAH, COR
    (5331, 5331, "Consumer Staples"),  # variety stores: WMT, COST, TGT, DG, DLTR
    (6324, 6324, "Health Care"),  # hospital & medical service plans: UNH, ELV, CI, CNC, HUM
    (6500, 6599, "Real Estate"),  # real estate operators and developers: CBRE, INVH
    (6798, 6798, "Real Estate"),  # REITs -- 26 of the S&P's 29 real estate names sit here
    (7320, 7320, "Financials"),  # credit reporting and ratings: SPGI, MCO
    (7370, 7370, "Communication"),  # the range says Technology; every S&P name here is media
    (7389, 7389, "Financials"),  # business services NEC, mostly payments: FIS, FISV, GPN, MSCI
    (7900, 7900, "Communication"),  # amusement & recreation: LYV, TKO
    (8731, 8731, "Health Care"),  # commercial biological research: IQV, CRL, INCY
    (100, 999, "Other"),
    (1000, 1499, "Energy & Mining"),
    (1500, 1799, "Industrials"),
    (2000, 2199, "Consumer Staples"),
    (2200, 2599, "Consumer Discretionary"),
    (2600, 2699, "Materials"),
    (2700, 2799, "Communication"),
    (2800, 2829, "Materials"),
    (2830, 2836, "Health Care"),
    (2840, 2899, "Consumer Staples"),
    (2900, 2999, "Energy & Mining"),
    (3000, 3499, "Materials"),
    (3500, 3569, "Industrials"),
    (3570, 3579, "Technology"),
    (3580, 3669, "Industrials"),
    (3670, 3699, "Technology"),
    (3700, 3799, "Consumer Discretionary"),
    # SIC 38xx is "instruments" in general, not medical devices, so it cannot map as one block:
    # 3812 is defence electronics (L3Harris), 382x industrial controls (Ametek, Trane) and
    # electrical test gear, 3827 optical (Coherent, KLA). Only 3826 and 384x-3851 are health care.
    (3800, 3824, "Industrials"),
    (3825, 3825, "Technology"),
    (3826, 3826, "Health Care"),  # laboratory analytical instruments -- life-science tools
    (3827, 3840, "Technology"),
    (3841, 3851, "Health Care"),  # surgical, orthopedic, dental, x-ray, electromedical, ophthalmic
    (3852, 3999, "Consumer Discretionary"),
    (4000, 4799, "Industrials"),
    (4800, 4899, "Communication"),
    (4900, 4999, "Utilities"),
    (5000, 5999, "Consumer Discretionary"),
    (6000, 6799, "Financials"),
    (7000, 7369, "Consumer Discretionary"),
    (7370, 7379, "Technology"),
    (7380, 7999, "Consumer Discretionary"),
    (8000, 8099, "Health Care"),
    (8100, 8999, "Industrials"),
]


def sic_to_sector(sic: Optional[int], security_type: Optional[str] = None) -> str:
    if security_type == "ETP":
        return "ETF / Fund"
    if sic is None:
        return "Unknown"
    for low, high, sector in SIC_RANGES:
        if low <= sic <= high:
            return sector
    return "Other"
