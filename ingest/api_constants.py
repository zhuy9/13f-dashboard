"""External API endpoints used by enrich.py."""

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# The older, plainer ticker list. It is a superset: it keeps companies that have deregistered
# and dropped out of company_tickers.json, which is the only way to sector a delisted holding.
SEC_TICKER_TXT_URL = "https://www.sec.gov/include/ticker.txt"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
