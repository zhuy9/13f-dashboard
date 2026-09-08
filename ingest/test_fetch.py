import pandas as pd

from fetch import collapse, edgar_ticker_hints, normalize


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
    lp = normalize(
        pd.DataFrame(
            [
                {
                    "Issuer": "HOWARD HUGHES",
                    "Class": "COM",
                    "Cusip": "44267D107",
                    "Ticker": "HHH",
                    "PutCall": "",
                    "Value": 1192581569,
                    "SharesPrnAmount": 18852064,
                }
            ]
        ),
        cik="1336528",
        short="Pershing",
        period="2026-03-31",
        filed_at="2026-05-15",
    )
    inc = normalize(
        pd.DataFrame(
            [
                {
                    "Issuer": "HOWARD HUGHES",
                    "Class": "COM",
                    "Cusip": "44267D107",
                    "Ticker": "HHH",
                    "PutCall": "",
                    "Value": 569340000,
                    "SharesPrnAmount": 9000000,
                }
            ]
        ),
        cik="1336528",
        short="Pershing",
        period="2026-03-31",
        filed_at="2026-05-15",
    )

    out = collapse(pd.concat([lp, inc], ignore_index=True))

    assert len(out) == 1, "the two filers' rows must merge into one base-table row"
    assert out.iloc[0]["shares"] == 27852064
    assert out.iloc[0]["value"] == 1192581569 + 569340000


def test_collapse_keeps_puts_calls_and_shares_on_the_same_cusip_apart():
    rows = pd.concat(
        [
            normalize(
                pd.DataFrame(
                    [
                        {
                            "Issuer": "META",
                            "Class": "COM",
                            "Cusip": "30303M102",
                            "Ticker": "META",
                            "PutCall": p,
                            "Value": 100,
                            "SharesPrnAmount": 10,
                        }
                    ]
                ),
                cik="1",
                short="M",
                period="2026-06-30",
                filed_at="2026-08-14",
            )
            for p in ["", "PUT", "CALL"]
        ],
        ignore_index=True,
    )

    out = collapse(rows)

    assert len(out) == 3


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
