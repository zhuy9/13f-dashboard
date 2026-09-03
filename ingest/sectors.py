"""SIC code to sector mapping."""

from typing import Optional

# (low, high, sector) — inclusive range, first match wins.
SIC_RANGES: list[tuple[int, int, str]] = [
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
    (3800, 3849, "Health Care"),
    (3850, 3999, "Consumer Discretionary"),
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
