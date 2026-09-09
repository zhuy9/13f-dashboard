"""GCS raw/parquet archive and Firestore document writer."""

import io
import json
import logging
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

import pandas as pd
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# Tables archived to parquet, one file per period. Dict-shaped per-period tables
# (manager_similarity, clusters) and tables without a period column (fastest_growing,
# latest-period-only by definition) aren't split-and-archived here -- archival only,
# not consumed by the live site. `# ponytail: JSON export for those if BigQuery needs them.`
_PARQUET_TABLES = [
    "holdings",
    "manager_quarter_summary",
    "manager_sector_exposure",
    "stock_quarter_summary",
    "stock_trend",
    "consensus_buys",
    "consensus_exits",
    "high_conviction",
    "biggest_new",
    "biggest_adds",
    "biggest_trims",
    "top_signals",
    "sector_rotation",
    "options_exposure",
]

_FIRESTORE_BATCH_SIZE = 400
# A commit is capped on total size as well as on operation count, and the size ceiling is the
# one that bites: at 12 quarters a manager_quarters doc runs to ~200 KiB, so 400 of them is
# tens of MB and Firestore answers "400 Transaction too big". 4 MB leaves generous headroom
# under the ~10 MiB limit -- the estimate below is a proxy, not the wire size.
_FIRESTORE_BATCH_BYTES = 4_000_000


def write_gcs(bucket, raw_by_filing: dict, tables: dict) -> None:
    """Raw 13F XML + one Parquet per table per period. Best-effort: log and continue per object."""
    for (cik, period, accession), raw_xml in raw_by_filing.items():
        if not raw_xml:
            continue
        # Named by accession, not just by period: an amended quarter has more than one filing
        # and the original must not be overwritten by the amendment that corrected it.
        path = f"raw/{cik}/{period}/{accession}.xml"
        try:
            bucket.blob(path).upload_from_string(raw_xml, content_type="application/xml")
        except Exception:
            logger.exception("GCS upload failed: %s", path)

    for name in _PARQUET_TABLES:
        df = tables.get(name)
        if df is None or df.empty or "period" not in df.columns:
            continue
        for period, period_df in df.groupby("period"):
            try:
                buf = io.BytesIO()
                period_df.to_parquet(buf, index=False)
                bucket.blob(f"parquet/{name}/{period}.parquet").upload_from_string(
                    buf.getvalue(), content_type="application/octet-stream"
                )
            except Exception:
                logger.exception("GCS upload failed: parquet/%s/%s", name, period)


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part.title() for part in rest)


def _clean(obj):
    """snake_case -> camelCase keys, recursively; NaN/NaT -> None."""
    if isinstance(obj, dict):
        return {_camel(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and pd.isna(obj):
        return None
    return obj


def _records(df: pd.DataFrame) -> list[dict]:
    return _clean(df.to_dict("records"))


def _commit_in_batches(db, writes: list[tuple[str, dict]]) -> None:
    """Flush on whichever ceiling comes first, operation count or total size."""
    batch, count, size = db.batch(), 0, 0
    for path, data in writes:
        doc_size = len(json.dumps(data, default=str))
        if count and (count >= _FIRESTORE_BATCH_SIZE or size + doc_size > _FIRESTORE_BATCH_BYTES):
            batch.commit()
            batch, count, size = db.batch(), 0, 0
        batch.set(db.document(path), data)
        count, size = count + 1, size + doc_size
    if count:
        batch.commit()


def _build_meta(tables: dict, funds: list[dict], periods: list[str]) -> dict:
    latest_period = periods[-1]
    managers = [{"cik": f["cik"], "short": f["short"], "name": f["name"], "cluster": f["cluster"]} for f in funds]
    clusters_at_latest = list(tables["clusters"].get(latest_period, {}).values())
    return {
        "latestPeriod": latest_period,
        "periods": periods,
        "managers": managers,
        "clusters": _clean(clusters_at_latest),
        # Which roster managers have a filing per quarter, so the site can say "no filing"
        # instead of rendering a missing filer as a manager holding zero of everything.
        "coverage": _clean(tables["coverage"]),
        "methodologyVersion": tables["methodology_version"],
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }


def _build_manager_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    manager_periods = tables["totals"].groupby("cik")["period"].apply(lambda s: sorted(s)).to_dict()
    return {
        f["cik"]: {
            "cik": f["cik"],
            "name": f["name"],
            "short": f["short"],
            "cluster": f["cluster"],
            "periods": manager_periods.get(f["cik"], []),
        }
        for f in funds
    }


def _build_manager_quarter_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    short_by_cik = {f["cik"]: f["short"] for f in funds}
    totals_idx = tables["totals"].set_index(["cik", "period"])
    mqs = tables["manager_quarter_summary"]
    mse = tables["manager_sector_exposure"]
    similarity = tables["manager_similarity"]
    filings = tables.get("filings")

    docs = {}
    for (cik, period), grp in mqs.groupby(["cik", "period"]):
        counts = grp["status"].value_counts()
        similar = similarity.get(period, {}).get("most_similar", {}).get(cik, [])
        docs[f"{cik}_{period}"] = {
            "priorPositions": _records(
                mqs[(mqs["cik"] == cik) & (mqs["period"] < period) & (mqs["kind"] == "EQUITY")]
                .sort_values("period")
                .drop_duplicates("symbol", keep="last")
                .assign(held=lambda d: d["value"] > 0)[["symbol", "period", "held"]]
            ),
            "filedAt": totals_idx.loc[(cik, period), "filed_at"],
            "totalValue": int(totals_idx.loc[(cik, period), "total_value"]),
            # The filing total covers every row. The equity value is the weight denominator,
            # so the two differ for any manager reporting options, notes, or warrants.
            "equityValue": int(totals_idx.loc[(cik, period), "equity_value"]),
            "count": int((grp["value"] > 0).sum()),
            "counts": {
                "new": int(counts.get("NEW", 0)),
                "added": int(counts.get("ADDED", 0)),
                "trimmed": int(counts.get("TRIMMED", 0)),
                "unchanged": int(counts.get("UNCHANGED", 0)),
                "soldOut": int(counts.get("SOLD_OUT", 0)),
            },
            # Carried once per document, not per position: one filing usually reports every
            # position, and a position's `accession` joins to this list.
            "filings": _filing_records(filings, cik, period),
            "positions": _records(grp.drop(columns=["cik", "period"])),
            "sectors": _records(mse[(mse["cik"] == cik) & (mse["period"] == period)].drop(columns=["cik", "period"])),
            "mostSimilar": [
                {"cik": s["cik"], "short": short_by_cik.get(s["cik"], s["cik"]), "score": s["score"]} for s in similar
            ],
        }
    return docs


def _filing_records(filings, cik: str, period: str) -> list[dict]:
    """The filings behind one manager-quarter: accession, EDGAR link, and amendment status.

    `filer_cik` differs from `cik` for a manager whose book is filed under an `aliases13f` CIK,
    which is exactly the case where a reader cannot otherwise find the filing on EDGAR.
    """
    if filings is None or not len(filings):
        return []
    mine = filings[(filings["cik"] == cik) & (filings["period"] == period)]
    return _records(mine.drop(columns=["cik", "period"]).sort_values("accession"))


def _build_stock_docs(tables: dict) -> dict[str, dict]:
    """Identity and trend only. The holder table for every quarter, newest included, lives in
    stock_quarters/ -- one publisher, so the two can never disagree."""
    trend = tables["stock_trend"]
    return {
        symbol: {
            "symbol": symbol,
            "name": meta["name"],
            "sector": meta["sector"],
            "kind": meta["kind"],
            "trend": _records(trend[trend["symbol"] == symbol].drop(columns=["symbol"])),
        }
        for symbol, meta in tables["symbols"].set_index("symbol").iterrows()
    }


def _build_stock_quarter_docs(tables: dict, funds: list[dict]) -> dict[str, dict]:
    short = {f["cik"]: f["short"] for f in funds}
    options = {(r.period, r.symbol): r for r in tables["options_exposure"].itertuples()}
    docs = {}
    for _, row in tables["stock_quarter_summary"].iterrows():
        period, symbol = row["period"], row["symbol"]
        opt = options.get((period, symbol))
        doc = _clean(row.drop(labels=["symbol", "name"]).to_dict())
        doc["options"] = {
            "calls": [{"cik": c, "short": short[c]} for c in opt.call_holders] if opt else [],
            "puts": [{"cik": c, "short": short[c]} for c in opt.put_holders] if opt else [],
        }
        ciks = {r["cik"] for r in doc["holders"] + doc["soldOut"]}
        doc["filings"] = [r for cik in sorted(ciks) for r in _filing_records(tables.get("filings"), cik, period)]
        docs[f"{symbol}_{period}"] = doc
    return docs


def _build_signals_docs(tables: dict, periods: list[str]) -> dict[str, dict]:
    # (Firestore field name, source table name) -- table names stay snake_case (Python side);
    # doc field names are camelCase (JS side), converted explicitly since these are top-level
    # document keys, not row fields that flow through _records()/_clean()'s recursive _camel().
    e_tables = [
        ("consensusBuys", "consensus_buys"),
        ("consensusExits", "consensus_exits"),
        ("highConviction", "high_conviction"),
        ("biggestNew", "biggest_new"),
        ("biggestAdds", "biggest_adds"),
        ("biggestTrims", "biggest_trims"),
        ("topSignals", "top_signals"),
    ]
    docs = {}
    for period in periods:
        doc = {
            field: _records(tables[table][tables[table]["period"] == period].drop(columns=["period"]))
            for field, table in e_tables
        }
        doc["fastestGrowing"] = _records(tables["fastest_growing"]) if period == periods[-1] else []

        rotation = tables["sector_rotation"]
        doc["sectorRotation"] = _records(rotation[rotation["period"] == period].drop(columns=["period"]))

        sim = tables["manager_similarity"].get(period, {"ciks": [], "matrix": [], "most_similar": {}})
        # Firestore forbids arrays nested directly inside arrays, so each row is a {values: [...]} map.
        doc["managerSimilarity"] = {"ciks": sim["ciks"], "matrix": [{"values": row} for row in sim["matrix"]]}

        opts = tables["options_exposure"]
        doc["optionsExposure"] = _records(opts[opts["period"] == period].drop(columns=["period"]))
        filings = tables.get("filings")
        doc["filings"] = _records(filings[filings["period"] == period]) if filings is not None else []
        doc["config"] = _clean(tables["signal_config"])
        docs[period] = doc
    return docs


def _build_holder_counts(tables: dict, latest_period: str) -> dict:
    """How many tracked managers held each symbol at the newest quarter. `ownership.py` reads
    this one doc per run to say what a 13D/13G lands on top of, which is the only place the two
    pipelines meet. A list of records, not a map: symbols include convertible-note descriptions
    like "COIN 0.5 06/01/26", and a "." in a Firestore field name is a field-path separator."""
    sqs = tables["stock_quarter_summary"]
    held = sqs[(sqs["period"] == latest_period) & (sqs["manager_count"] > 0)]
    counts = held[["symbol", "manager_count"]].rename(columns={"manager_count": "n"})
    return {"period": latest_period, "counts": _records(counts)}


def read_holder_counts(db) -> Optional[dict[str, int]]:
    """The other side of `_build_holder_counts`, for `ownership.py`. None -- not {} -- when the
    doc is absent because ingest has never run: no answer is not the same answer as zero."""
    meta = db.document("meta/latest").get()
    dataset = (meta.to_dict() or {}).get("datasetId") if meta.exists else None
    path = f"datasets/{dataset}/meta/holder_counts" if dataset else "meta/holder_counts"
    snap = db.document(path).get()
    doc = snap.to_dict() if snap.exists else None
    return {r["symbol"]: r["n"] for r in doc["counts"]} if doc else None


def write_firestore(db, tables: dict, funds: list[dict], periods: list[str]) -> None:
    """Publish a complete snapshot, then atomically switch the reader's pointer."""
    dataset_id = uuid4().hex
    owned = {
        "managers": _build_manager_docs(tables, funds),
        "manager_quarters": _build_manager_quarter_docs(tables, funds),
        # quote() so a ticker with a "/" (SPAC units/warrants: "ABC/U", "ABC/WS") can't
        # split into extra Firestore path segments. Ordinary tickers are untouched.
        "stocks": {quote(symbol, safe=""): doc for symbol, doc in _build_stock_docs(tables).items()},
        "signals": _build_signals_docs(tables, periods),
        "stock_quarters": {quote(key, safe=""): doc for key, doc in _build_stock_quarter_docs(tables, funds).items()},
    }
    # symbols is its own doc: every page reads meta/latest, but only the search box needs the
    # ~2,300-entry symbol list, which is most of what meta/latest would otherwise weigh.
    writes: list[tuple[str, dict]] = [
        ("meta/symbols", {"symbols": _records(tables["symbols"][["symbol", "name", "sector"]])}),
        ("meta/holder_counts", _build_holder_counts(tables, periods[-1])),
    ]
    for collection, docs in owned.items():
        writes += [(f"{collection}/{doc_id}", doc) for doc_id, doc in docs.items()]
    _commit_in_batches(db, [(f"datasets/{dataset_id}/{path}", doc) for path, doc in writes])
    _commit_in_batches(db, [("meta/latest", {**_build_meta(tables, funds, periods), "datasetId": dataset_id})])
    # ponytail: retain snapshots for pinned readers; add age-based cleanup if storage grows.
