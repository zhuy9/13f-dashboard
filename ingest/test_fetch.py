import pandas as pd

from fetch import edgar_ticker_hints, normalize


def test_normalize_uppercases_merges_drops_and_ints():
    raw = pd.DataFrame(
        [
            {
                "Issuer": "APPLE INC",
                "Class": "COM",
                "Cusip": "037833100",
                "Ticker": "AAPL",
                "PutCall": "",
                "Value": 1000,
                "SharesPrnAmount": 10,
            },
            {
                "Issuer": "APPLE INC",
                "Class": "COM",
                "Cusip": "037833100",
                "Ticker": "AAPL",
                "PutCall": "",
                "Value": 500,
                "SharesPrnAmount": 5,
            },
            {
                "Issuer": "MICRON TECH INC",
                "Class": "COM",
                "Cusip": "595112103",
                "Ticker": "MU",
                "PutCall": "put",
                "Value": 200,
                "SharesPrnAmount": 20,
            },
            {
                "Issuer": "BLANK CUSIP CO",
                "Class": "COM",
                "Cusip": "",
                "Ticker": "",
                "PutCall": "",
                "Value": 999,
                "SharesPrnAmount": 99,
            },
            {
                "Issuer": "META PLATFORMS INC",
                "Class": "COM",
                "Cusip": "30303M102",
                "Ticker": "META",
                "PutCall": "Call",
                "Value": 300,
                "SharesPrnAmount": 30,
            },
            {
                "Issuer": "TAIWAN SEMI",
                "Class": "SPONS ADS",
                "Cusip": "874039100",
                "Ticker": "TSM",
                "PutCall": "",
                "Value": 400,
                "SharesPrnAmount": 40,
            },
        ]
    )

    out = normalize(raw, cik="1234567", short="Test Fund", period="2026-06-30", filed_at="2026-08-14")

    assert set(out["cusip"]) == {"037833100", "595112103", "30303M102", "874039100"}

    aapl = out[out["cusip"] == "037833100"].iloc[0]
    assert aapl["value"] == 1500
    assert aapl["shares"] == 15
    assert pd.isna(aapl["put_call"])

    mu = out[out["cusip"] == "595112103"].iloc[0]
    assert mu["put_call"] == "PUT"

    meta = out[out["cusip"] == "30303M102"].iloc[0]
    assert meta["put_call"] == "CALL"

    assert out["value"].dtype.kind in "iu"
    assert out["shares"].dtype.kind in "iu"
    assert (out["cik"] == "1234567").all()
    assert (out["period"] == "2026-06-30").all()


def test_edgar_ticker_hints_skips_blank_and_missing_cusip():
    raw = pd.DataFrame(
        [
            {"Cusip": "037833100", "Ticker": "AAPL"},
            {"Cusip": "H1467J104", "Ticker": "CB"},
            {"Cusip": "999999999", "Ticker": ""},
            {"Cusip": "", "Ticker": "XYZ"},
        ]
    )
    hints = edgar_ticker_hints(raw)
    assert hints == {"037833100": "AAPL", "H1467J104": "CB"}
