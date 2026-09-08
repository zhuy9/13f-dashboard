from sectors import sic_to_sector


def test_etp_is_etf_fund():
    assert sic_to_sector(6221, "ETP") == "ETF / Fund"


def test_none_sic_is_unknown():
    assert sic_to_sector(None) == "Unknown"


def test_in_range_sic_maps_to_sector():
    assert sic_to_sector(3674) == "Technology"
    assert sic_to_sector(6021) == "Financials"


def test_out_of_range_sic_is_other():
    assert sic_to_sector(9999) == "Other"


def test_sic_38xx_is_instruments_not_all_medical():
    """3800-3849 used to map wholesale to Health Care, which filed KLA, Coherent, L3Harris and
    Trane under it. Only the laboratory and 384x-3851 medical codes belong there."""
    assert sic_to_sector(3827) == "Technology"  # optical instruments: COHR, KLAC
    assert sic_to_sector(3825) == "Technology"  # electrical test: AEHR, FEIM
    assert sic_to_sector(3829) == "Technology"  # measuring devices NEC: ONTO
    assert sic_to_sector(3812) == "Industrials"  # search/detection/navigation: LHX, DRS
    assert sic_to_sector(3822) == "Industrials"  # auto controls: TT
    assert sic_to_sector(3823) == "Industrials"  # industrial instruments: AME

    assert sic_to_sector(3826) == "Health Care"  # laboratory analytical: Agilent
    assert sic_to_sector(3841) == "Health Care"  # surgical & medical instruments
    assert sic_to_sector(3845) == "Health Care"  # electromedical
    assert sic_to_sector(3851) == "Health Care"  # ophthalmic goods: ALC, BLCO, COO
    assert sic_to_sector(3861) == "Consumer Discretionary"  # photographic equipment


def test_reits_are_real_estate_not_financials():
    """GICS split Real Estate out of Financials in 2016; SIC 6798 sits inside the 6000-6799
    financials range, so REITs need an explicit carve above it."""
    assert sic_to_sector(6798) == "Real Estate"
    assert sic_to_sector(6500) == "Real Estate"
    assert sic_to_sector(6021) == "Financials"


def test_measured_carves_beat_their_enclosing_range():
    assert sic_to_sector(5331) == "Consumer Staples"  # WMT, COST -- range says Consumer Disc
    assert sic_to_sector(6324) == "Health Care"  # UNH, ELV -- range says Financials
    assert sic_to_sector(4922) == "Energy & Mining"  # KMI, WMB -- range says Utilities
    assert sic_to_sector(4923) == "Utilities"  # gas distribution still is one
