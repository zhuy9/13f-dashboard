import pandas as pd

from fetch import BASE_COLUMNS, collapse, edgar_ticker_hints, normalize


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


def test_collapse_sums_one_book_split_across_two_filer_ciks():
    """Pershing's 2026-03-31 book: the LP reported 18,852,064 HHH shares and Pershing Square Inc
    another 9,000,000. The combined 2026-06-30 filing shows 27,852,064 -- the parts are additive."""

    def row(value: int, shares: int) -> dict:
        return {
            "cik": "1336528", "short": "Pershing", "period": "2026-03-31", "filed_at": "2026-05-15",
            "cusip": "44267T102", "name": "HOWARD HUGHES", "cls": "COM",
            "value": value, "shares": shares, "put_call": None,
        }  # fmt: skip

    out = collapse(pd.DataFrame([row(1192581569, 18852064), row(569340000, 9000000)], columns=BASE_COLUMNS))

    assert len(out) == 1, "the two filers' rows must merge into one base-table row"
    assert out.iloc[0]["shares"] == 27852064
    assert out.iloc[0]["value"] == 1192581569 + 569340000


def test_edgar_ticker_hints_skips_blanks_missing_cusips_and_stringified_nulls():
    """A stringified null must never become a hint. A hint suppresses the OpenFIGI lookup and
    then becomes the symbol, so every CUSIP sharing one merges into a single fake stock -- live,
    "NONE" collapsed 119 securities into a $5.9B stocks/NONE holding six managers."""
    raw = pd.DataFrame(
        [
            {"Cusip": "037833100", "Ticker": "AAPL"},
            {"Cusip": "H1467J104", "Ticker": "CB"},
            {"Cusip": "999999999", "Ticker": ""},
            {"Cusip": "", "Ticker": "XYZ"},
            {"Cusip": "111111111", "Ticker": None},
            {"Cusip": "222222222", "Ticker": float("nan")},
            {"Cusip": "333333333", "Ticker": "none"},
        ]
    )
    hints = edgar_ticker_hints(raw)
    assert hints == {"037833100": "AAPL", "H1467J104": "CB"}
