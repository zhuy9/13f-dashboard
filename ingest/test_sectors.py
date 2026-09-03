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
