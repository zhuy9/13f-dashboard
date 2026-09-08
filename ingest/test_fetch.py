import pandas as pd

from fetch import BASE_COLUMNS, Filing, collapse, edgar_ticker_hints, normalize, resolve_amendments


def _filing(
    accession: str = "0001-26-000001",
    url: str = "https://www.sec.gov/Archives/edgar/data/1234567/0001-26-000001-index.html",
    period: str = "2026-06-30",
    filed_at: str = "2026-08-14",
    is_amendment: bool = False,
    amendment_type=None,
    amendment_no: int = 0,
    holdings: pd.DataFrame = None,
) -> Filing:
    return Filing(accession, url, period, filed_at, is_amendment, amendment_type, amendment_no, None, holdings)


def _holdings(*cusips: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Issuer": f"CO {c}",
                "Class": "COM",
                "Cusip": c,
                "Ticker": c[:4],
                "PutCall": "",
                "Value": 1000,
                "SharesPrnAmount": 10,
            }
            for c in cusips
        ]
    )


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

    out = normalize(raw, cik="1234567", short="Test Fund", filing=_filing())

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
            "accession": "0001-26-000001", "disclosed_by_amendment": False,
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


def _kept_cusips(kept) -> list[str]:
    return sorted(c for _, df in kept for c in df["Cusip"])


def test_an_original_filing_alone_is_kept_as_is():
    kept, notes = resolve_amendments([_filing(holdings=_holdings("AAA", "BBB"))])

    assert _kept_cusips(kept) == ["AAA", "BBB"]
    assert notes == []


def test_a_restatement_replaces_the_original_it_corrects():
    """A RESTATEMENT re-files the whole report. Unioning it with the original would double
    every position the manager did not change."""
    original = _filing("acc1", holdings=_holdings("AAA", "BBB"))
    restated = _filing("acc2", is_amendment=True, amendment_type="RESTATEMENT", amendment_no=1, holdings=_holdings("AAA"))

    kept, notes = resolve_amendments([restated, original])

    assert _kept_cusips(kept) == ["AAA"]
    assert [f.accession for f, _ in kept] == ["acc2"]
    assert notes == []


def test_an_additive_amendment_unions_with_the_original_instead_of_replacing_it():
    """NEW HOLDINGS carries only the positions that were confidential. Treating it as a
    restatement would throw the real portfolio away and leave one holding behind."""
    original = _filing("acc1", holdings=_holdings("AAA", "BBB"))
    added = _filing("acc2", is_amendment=True, amendment_type="NEW HOLDINGS", amendment_no=1, holdings=_holdings("CCC"))

    kept, notes = resolve_amendments([original, added])

    assert _kept_cusips(kept) == ["AAA", "BBB", "CCC"]
    assert notes == []


def test_an_additive_amendment_that_re_reports_a_held_position_counts_it_once():
    original = _filing("acc1", holdings=_holdings("AAA", "BBB"))
    added = _filing("acc2", is_amendment=True, amendment_type="NEW HOLDINGS", amendment_no=1, holdings=_holdings("BBB", "CCC"))

    kept, notes = resolve_amendments([original, added])

    assert _kept_cusips(kept) == ["AAA", "BBB", "CCC"]
    assert "counted once" in notes[0]


def test_resolving_the_same_accessions_twice_is_idempotent():
    """The pipeline is stateless and refetches every window, so the same filings are resolved
    on every run. A duplicate accession also arrives for real when two aliases13f CIKs list
    the same filing."""
    filings = [
        _filing("acc1", holdings=_holdings("AAA", "BBB")),
        _filing("acc2", is_amendment=True, amendment_type="NEW HOLDINGS", amendment_no=1, holdings=_holdings("CCC")),
    ]

    once, _ = resolve_amendments(filings)
    twice, _ = resolve_amendments(filings + filings)

    assert _kept_cusips(once) == _kept_cusips(twice) == ["AAA", "BBB", "CCC"]


def test_an_amendment_with_no_type_is_skipped_and_reported_never_guessed():
    """Guessing RESTATEMENT deletes a portfolio; guessing NEW HOLDINGS double-counts one.
    Neither is allowed to happen quietly."""
    original = _filing("acc1", holdings=_holdings("AAA", "BBB"))
    untyped = _filing("acc2", is_amendment=True, amendment_type=None, amendment_no=1, holdings=_holdings("ZZZ"))

    kept, notes = resolve_amendments([original, untyped])

    assert _kept_cusips(kept) == ["AAA", "BBB"]
    assert "no type" in notes[0] and "skipped" in notes[0]


def test_a_holding_only_an_amendment_disclosed_is_labelled_as_disclosed_not_as_bought():
    """Filing disclosure is not a trade date. A previously-confidential position was held all
    along, so the row says how it came to light and nothing about when it was acquired."""
    added = _filing("acc2", is_amendment=True, amendment_type="NEW HOLDINGS", amendment_no=1, holdings=_holdings("CCC"))

    rows = normalize(added.holdings, cik="1234567", short="Test Fund", filing=added)

    assert rows.iloc[0]["disclosed_by_amendment"]
    assert rows.iloc[0]["accession"] == "acc2"
    assert rows.iloc[0]["filed_at"] == "2026-08-14"  # when it was filed, not when it was bought


def test_only_amended_filings_in_the_window_is_reported():
    restated = _filing("acc2", is_amendment=True, amendment_type="RESTATEMENT", amendment_no=1, holdings=_holdings("AAA"))

    kept, notes = resolve_amendments([restated])

    assert _kept_cusips(kept) == ["AAA"]
    assert "no original" in notes[0]
